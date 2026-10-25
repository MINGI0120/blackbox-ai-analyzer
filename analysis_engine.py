"""Headless adapter of the supplied RoadLens Streamlit analysis loop.
The detection, trajectory, lane, motion and decision rules are preserved.
"""
import math
import subprocess
from pathlib import Path
from collections import defaultdict, deque
import cv2
import numpy as np
from ultralytics import YOLO
from accident_classifier import recommend_accident_type
from ego_motion_analyzer import EgoMotionAnalyzer
from fault_estimator import estimate_fault_ratio
from fault_modifiers import detect_fault_modifiers
from lane_analyzer import LaneAnalyzer
from fault_rules import get_fault_rule, recommend_rule_from_situation
from risk_analyzer import analyze_frame_risk

class AnalysisCancelled(Exception):
    pass

class Progress:
    def __init__(self, callback): self.callback=callback; self.value=0
    def progress(self, value): self.value=min(.94, value*.94)
    def write(self, message): self.callback(self.value, message)

def get_direction(points, movement_threshold):
    if len(points) < 2:
        return "판단 불가"

    start_x, start_y = points[0]
    end_x, end_y = points[-1]

    move_x = end_x - start_x
    move_y = end_y - start_y

    if abs(move_x) < movement_threshold and abs(move_y) < movement_threshold:
        return "움직임 적음"

    if abs(move_x) > abs(move_y):
        if move_x > 0:
            return "화면 오른쪽으로 이동"

        return "화면 왼쪽으로 이동"

    if move_y > 0:
        return "화면 아래쪽으로 이동"

    return "화면 위쪽으로 이동"

def is_valid_detection(box, class_name, frame_width, frame_height):
    if len(box) != 4:
        return False

    x1, y1, x2, y2 = box
    box_width_ratio = max(0, x2 - x1) / max(frame_width, 1)
    box_height_ratio = max(0, y2 - y1) / max(frame_height, 1)
    top_ratio = y1 / max(frame_height, 1)
    bottom_ratio = y2 / max(frame_height, 1)

    # 블랙박스 화면 아래쪽의 보닛·대시보드·와이퍼가 큰 차량으로
    # 오인되는 경우를 제거한다. 실제 오토바이처럼 작은 객체는 유지한다.
    dashboard_false_positive = (
        class_name in {"car", "bus", "truck"}
        and bottom_ratio >= 0.84
        and top_ratio >= 0.42
        and box_width_ratio >= 0.40
        and box_height_ratio >= 0.22
    )

    return not dashboard_false_positive

def analyze_video(input_path, directory, situation, selected_rule_key, apply_video_recommendation,
                  modifier_target, callback, cancelled, model_path):
    directory=Path(directory)
    selected_rule=get_fault_rule(selected_rule_key)
    situation_recommendation=recommend_rule_from_situation(situation)
    detected_modifiers=detect_fault_modifiers(situation)
    output_path=str(directory/'annotated-raw.mp4')
    video=cv2.VideoCapture(str(input_path))
    if not video.isOpened():
        video.release()
        raise ValueError('영상을 읽을 수 없습니다. MP4 영상을 사용해 주세요.')
    width=video.get(cv2.CAP_PROP_FRAME_WIDTH)
    height=video.get(cv2.CAP_PROP_FRAME_HEIGHT)
    frames=video.get(cv2.CAP_PROP_FRAME_COUNT)
    fps=video.get(cv2.CAP_PROP_FPS)
    if not all(math.isfinite(n) for n in (width,height,frames,fps)) or not 16<=width<=3840 or not 16<=height<=2160 or fps<=0 or frames<=0 or frames/fps>180 or frames>12000:
        video.release()
        raise ValueError('최대 4K, 3분, 12,000프레임 이내 영상을 사용해 주세요.')
    writer=None
    try:
        fps = video.get(cv2.CAP_PROP_FPS)

        if fps <= 0:
            fps = 25

        width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")

        writer = cv2.VideoWriter(
            output_path,
            fourcc,
            fps,
            (width, height)
        )

        model = YOLO(str(model_path))

        target_objects = [
            "person",
            "car",
            "bus",
            "truck",
            "motorcycle",
            "bicycle",
            "traffic light",
            "stop sign"
        ]

        maximum_counts = {
            object_name: 0
            for object_name in target_objects
        }

        tracked_ids = set()
        track_history = defaultdict(lambda: deque(maxlen=60))
        track_box_history = defaultdict(lambda: deque(maxlen=60))
        track_classes = {}
        frame_vehicle_history = []
        ego_motion_analyzer = EgoMotionAnalyzer(sample_interval=3)
        lane_analyzer = LaneAnalyzer(analysis_width=1280)

        movement_threshold = max(width, height) * 0.02
        if not writer.isOpened():
            raise ValueError('분석 영상 파일을 만들 수 없습니다.')
        progress_bar=Progress(callback)
        status_text=progress_bar
        frame_number=0
        last_frame=None
        highest_risk_event=None
        highest_risk_frame=None
        pair_distance_history={}
        while True:
            if cancelled():
                raise AnalysisCancelled()
            if frame_number >= 12000:
                raise ValueError("영상이 너무 깁니다. 3분 이내의 구간으로 잘라 주세요.")
            success, frame = video.read()

            if not success:
                break

            ego_motion_analyzer.update(frame)
            current_lane_result = lane_analyzer.update(frame)

            result = model.track(
                source=frame,
                conf=0.35,
                persist=True,
                tracker="bytetrack.yaml",
                verbose=False
            )[0]

            if result.boxes is not None and len(result.boxes) > 0:
                original_boxes = result.boxes.xyxy.cpu().tolist()
                original_classes = result.boxes.cls.int().cpu().tolist()
                valid_indices = []

                for detection_index, (
                    detection_box,
                    class_number
                ) in enumerate(zip(original_boxes, original_classes)):
                    class_name = result.names[class_number]

                    if is_valid_detection(
                        detection_box,
                        class_name,
                        width,
                        height
                    ):
                        valid_indices.append(detection_index)

                result.boxes = result.boxes[valid_indices]

            current_counts = {
                object_name: 0
                for object_name in target_objects
            }

            frame_detections = []
            frame_vehicles = []
            current_frame_risk = None

            if result.boxes is not None:
                class_numbers = (
                    result.boxes.cls
                    .int()
                    .cpu()
                    .tolist()
                )

                for class_number in class_numbers:
                    object_name = result.names[class_number]

                    if object_name in current_counts:
                        current_counts[object_name] += 1

                xyxy_boxes = (
                    result.boxes.xyxy
                    .cpu()
                    .tolist()
                )

                # 추적 번호가 없어도 프레임에 나온 차량은 모두 기록
                for xyxy_box, class_number in zip(
                    xyxy_boxes,
                    class_numbers
                ):
                    object_name = result.names[class_number]

                    if object_name in {
                        "car",
                        "bus",
                        "truck",
                        "motorcycle"
                    }:
                        frame_vehicles.append(
                            {
                                "class_name": object_name,
                                "box": xyxy_box
                            }
                        )

                if result.boxes.id is not None:
                    xywh_boxes = (
                        result.boxes.xywh
                        .cpu()
                        .tolist()
                    )

                    track_ids = (
                        result.boxes.id
                        .int()
                        .cpu()
                        .tolist()
                    )

                    for (
                        xywh_box,
                        xyxy_box,
                        track_id,
                        class_number
                    ) in zip(
                        xywh_boxes,
                        xyxy_boxes,
                        track_ids,
                        class_numbers
                    ):
                        center_x = int(xywh_box[0])
                        center_y = int(xywh_box[1])
                        object_name = result.names[class_number]

                        tracked_ids.add(track_id)
                        track_classes[track_id] = object_name

                        track_history[track_id].append(
                            (center_x, center_y)
                        )

                        track_box_history[track_id].append(
                            xyxy_box
                        )

                        frame_detections.append(
                            {
                                "track_id": track_id,
                                "class_name": object_name,
                                "box": xyxy_box
                            }
                        )

                    current_frame_risk = analyze_frame_risk(
                        frame_detections,
                        width,
                        height,
                        pair_distance_history
                    )

            frame_vehicle_history.append(frame_vehicles)

            for object_name, count in current_counts.items():
                maximum_counts[object_name] = max(
                    maximum_counts[object_name],
                    count
                )

            analyzed_frame = result.plot()
            analyzed_frame = lane_analyzer.draw_overlay(
                analyzed_frame,
                current_lane_result
            )

            for track_id, points in track_history.items():
                if len(points) >= 2:
                    path_points = np.array(
                        points,
                        dtype=np.int32
                    ).reshape((-1, 1, 2))

                    cv2.polylines(
                        analyzed_frame,
                        [path_points],
                        isClosed=False,
                        color=(0, 255, 0),
                        thickness=3
                    )

            if current_frame_risk is not None:
                cv2.putText(
                    analyzed_frame,
                    (
                        "RISK "
                        f"{current_frame_risk['score']} "
                        f"({current_frame_risk['level']})"
                    ),
                    (20, 45),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 0, 255),
                    3
                )

                if (
                    highest_risk_event is None
                    or current_frame_risk["score"]
                    > highest_risk_event["score"]
                ):
                    highest_risk_event = (
                        current_frame_risk.copy()
                    )

                    highest_risk_event["frame_number"] = (
                        frame_number + 1
                    )

                    highest_risk_event["time_seconds"] = round(
                        frame_number / fps,
                        2
                    )

                    highest_risk_frame = analyzed_frame.copy()

            writer.write(analyzed_frame)
            last_frame = analyzed_frame

            frame_number += 1

            if total_frames > 0:
                progress = min(
                    frame_number / total_frames,
                    1.0
                )

                progress_bar.progress(progress)

            status_text.write(
                f"분석 중: {frame_number} / "
                f"{total_frames} 프레임"
            )
    finally:
        video.release()
        if writer is not None: writer.release()
    if frame_number==0:
        raise ValueError('재생 가능한 영상 프레임이 없습니다.')
    if cancelled(): raise AnalysisCancelled()
    ego_motion_result=ego_motion_analyzer.get_result()
    lane_analysis_result=lane_analyzer.get_result()
    video_recommendation = recommend_accident_type(
        track_history,
        track_box_history,
        track_classes,
        width,
        height,
        frame_vehicle_history,
        ego_motion_result,
        lane_analysis_result,
        situation=situation,
    )

    recommendation_key = video_recommendation.get("rule_key")
    recommendation_confidence = video_recommendation.get(
        "confidence",
        0
    )

    situation_rule_key = (
        situation_recommendation.get("rule_key")
        if situation_recommendation is not None
        else None
    )
    situation_video_supported = True

    if situation_rule_key in {
        "uturn_vs_motorcycle",
        "signal_uturn_vs_motorcycle"
    }:
        situation_video_supported = (
            ego_motion_result.get("maneuver") == "u_turn"
            and ego_motion_result.get("confidence", 0) >= 60
        )

    situation_rule_applied = (
        situation_recommendation is not None
        and not video_recommendation.get('requires_rule_review', False)
        and situation_rule_key is not None
        and situation_recommendation.get("confidence", 0) >= 60
        and situation_video_supported
    )

    video_rule_applied = (
        apply_video_recommendation
        and not situation_rule_applied
        and recommendation_key is not None
        and recommendation_confidence >= 60
    )

    analysis_on_hold = (
        apply_video_recommendation
        and not situation_rule_applied
        and not video_rule_applied
    )

    if situation_rule_applied:
        analysis_rule_key = situation_recommendation["rule_key"]
        analysis_rule = get_fault_rule(
            analysis_rule_key
        )
    elif video_rule_applied:
        analysis_rule_key = recommendation_key
        analysis_rule = get_fault_rule(
            analysis_rule_key
        )
    else:
        analysis_rule_key = selected_rule_key
        analysis_rule = selected_rule
    fault_estimate=None
    if not analysis_on_hold:
        fault_estimate = estimate_fault_ratio(
            rule_key=analysis_rule_key,
            rule=analysis_rule,
            situation=situation,
            video_recommendation=video_recommendation,
            ego_motion=ego_motion_result,
            highest_risk_event=highest_risk_event,
            lane_analysis=lane_analysis_result,
            detected_modifiers=detected_modifiers,
            modifier_target=modifier_target,
        )
    callback(.96, '분석 영상을 브라우저 재생 형식으로 저장하고 있습니다.')
    import imageio_ffmpeg
    encoded=directory/'analyzed.mp4'
    command=[imageio_ffmpeg.get_ffmpeg_exe(),'-y','-i',output_path,'-an','-c:v','libx264','-preset','fast','-crf','24','-pix_fmt','yuv420p','-vf','pad=ceil(iw/2)*2:ceil(ih/2)*2','-movflags','+faststart',str(encoded)]
    process=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        while process.poll() is None:
            if cancelled():
                process.terminate();process.wait(timeout=10)
                raise AnalysisCancelled()
            try: process.wait(timeout=.5)
            except subprocess.TimeoutExpired: pass
        if process.returncode: raise ValueError('분석 영상 인코딩에 실패했습니다.')
    finally:
        if process.poll() is None: process.kill();process.wait()
    Path(output_path).unlink(missing_ok=True)
    if highest_risk_frame is not None:
        cv2.imwrite(str(directory/'risk.jpg'),highest_risk_frame)
    return {
        'status':'held' if analysis_on_hold else 'complete',
        'situation':situation,'frames':frame_number,'fps':fps,
        'objects':{k:v for k,v in maximum_counts.items() if v>0},
        'tracked_objects':len(tracked_ids),'risk':highest_risk_event,
        'lane':lane_analysis_result,'ego':ego_motion_result,
        'recommendation':video_recommendation,'rule':analysis_rule,
        'rule_source':'unresolved' if analysis_on_hold else 'situation' if situation_rule_applied else 'video' if video_rule_applied else 'manual',
        'fault':fault_estimate,'modifiers':detected_modifiers,
        'movement':[{'id':i,'class':track_classes.get(i,'unknown'),'direction':get_direction(track_history[i],movement_threshold)} for i in sorted(tracked_ids)],
        'notice':'제공된 프로그램의 추정 결과입니다. 신뢰도는 프로그램 내부 점수이며 통계적으로 검증된 정확도가 아닙니다. 실제 과실 판단을 대신하지 않습니다.'
    }
