import os
from collections import defaultdict, deque

import cv2
import numpy as np
import streamlit as st
from ultralytics import YOLO

from accident_classifier import recommend_accident_type
from fault_modifiers import (
    calculate_adjusted_fault,
    detect_fault_modifiers
)
from fault_rules import get_fault_rule, get_rule_options
from risk_analyzer import analyze_frame_risk


st.set_page_config(
    page_title="AI 블랙박스 사고 분석",
    page_icon="🚗",
    layout="wide"
)


@st.cache_resource
def load_model():
    return YOLO("yolo11n.pt")


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


st.title("🚗 AI 블랙박스 사고 분석")

st.write(
    "블랙박스 영상과 사고 상황을 입력하면 AI가 객체의 종류, "
    "이동 경로, 위험 장면 및 예상 과실비율을 분석합니다."
)

st.warning(
    "분석 결과는 참고용 예상이며, 실제 과실비율은 사고 당시의 신호, "
    "속도, 도로 상태와 보험사·경찰·법원의 판단에 따라 달라질 수 있습니다."
)

rule_options = get_rule_options()

selected_rule_name = st.selectbox(
    "직접 선택 또는 AI 추천 실패 시 사용할 사고 유형",
    options=list(rule_options.keys()),
    help=(
        "AI 영상 추천의 신뢰도가 낮거나 자동 적용을 끈 경우 "
        "이 사고 유형을 사용합니다."
    )
)

selected_rule_key = rule_options[selected_rule_name]
selected_rule = get_fault_rule(selected_rule_key)

apply_video_recommendation = st.checkbox(
    "AI가 영상에서 추천한 사고 유형을 과실비율 계산에 적용",
    value=True,
    help=(
        "영상 추천 신뢰도가 60% 이상일 때만 자동으로 적용하며, "
        "그보다 낮으면 직접 선택한 사고 유형을 사용합니다."
    )
)

with st.expander("선택한 사고 유형의 기준 보기"):
    st.write(f"**공식 기준 도표:** {selected_rule['chart']}")
    st.write(f"**차량 A:** {selected_rule['vehicle_a']}")
    st.write(f"**차량 B:** {selected_rule['vehicle_b']}")
    st.write(
        f"**기본 과실비율:** "
        f"{selected_rule['vehicle_a']} {selected_rule['fault_a']}% / "
        f"{selected_rule['vehicle_b']} {selected_rule['fault_b']}%"
    )

uploaded_video = st.file_uploader(
    "블랙박스 영상을 선택하세요",
    type=["mp4", "avi", "mov", "mkv"]
)

situation = st.text_area(
    "사고 상황을 자세히 입력하세요",
    placeholder=(
        "예: 상대 차량이 제한속도보다 20km 이상 과속하면서 "
        "차로를 변경해 충돌했습니다."
    ),
    height=150
)

detected_modifiers = detect_fault_modifiers(situation)
modifier_target = None

if detected_modifiers:
    st.subheader("🔎 사고 설명에서 발견된 수정 요소")

    for modifier in detected_modifiers:
        st.warning(
            f"{modifier['name']} · {modifier['level']} · "
            f"최대 +{modifier['fault_addition']}%\n\n"
            f"{modifier['reason']}"
        )

    modifier_target_option = st.selectbox(
        "이 수정 요소는 어느 차량에 해당합니까?",
        options=[
            "수정 요소를 적용하지 않음",
            "차량 A에 적용",
            "차량 B에 적용"
        ],
        help=(
            "사고 설명만으로 위반 차량을 확정할 수 없으므로 "
            "증거를 확인한 후 선택해주세요."
        )
    )

    if modifier_target_option.startswith("차량 A"):
        modifier_target = "A"

    elif modifier_target_option.startswith("차량 B"):
        modifier_target = "B"

if uploaded_video is not None:
    st.subheader("업로드한 영상")
    st.video(uploaded_video)

if st.button("AI 사고 분석 시작", type="primary"):
    if uploaded_video is None:
        st.error("블랙박스 영상을 먼저 선택해주세요.")

    elif not situation.strip():
        st.error("사고 상황을 입력해주세요.")

    else:
        os.makedirs("temp", exist_ok=True)

        input_path = os.path.join("temp", "uploaded_video.mp4")
        output_path = os.path.join("temp", "analyzed_video.mp4")

        with open(input_path, "wb") as file:
            file.write(uploaded_video.getbuffer())

        video = cv2.VideoCapture(input_path)

        if not video.isOpened():
            st.error("영상을 불러오지 못했습니다.")

        else:
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

            model = load_model()

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

            movement_threshold = max(width, height) * 0.02

            progress_bar = st.progress(0)
            status_text = st.empty()

            frame_number = 0
            last_frame = None

            highest_risk_event = None
            highest_risk_frame = None
            pair_distance_history = {}

            with st.spinner(
                "AI가 영상, 이동 경로와 위험 장면을 분석하고 있습니다..."
            ):
                while True:
                    success, frame = video.read()

                    if not success:
                        break

                    result = model.track(
                        source=frame,
                        device=0,
                        conf=0.35,
                        persist=True,
                        tracker="bytetrack.yaml",
                        verbose=False
                    )[0]

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

            video.release()
            writer.release()

            progress_bar.progress(1.0)

            status_text.success(
                "영상 객체, 이동 경로 및 위험 장면 분석이 완료되었습니다."
            )

            st.subheader("AI 탐지 및 추적 결과")

            detected_objects = {
                name: count
                for name, count in maximum_counts.items()
                if count > 0
            }

            if detected_objects:
                columns = st.columns(len(detected_objects))

                for column, (name, count) in zip(
                    columns,
                    detected_objects.items()
                ):
                    column.metric(name, count)

            else:
                st.info("주요 도로 객체가 탐지되지 않았습니다.")

            st.metric(
                "추적된 객체 번호 수",
                len(tracked_ids)
            )

            movement_rows = []

            for track_id in sorted(tracked_ids):
                points = track_history[track_id]

                movement_rows.append(
                    {
                        "객체 번호": track_id,
                        "객체 종류": track_classes.get(
                            track_id,
                            "unknown"
                        ),
                        "이동 방향": get_direction(
                            points,
                            movement_threshold
                        ),
                        "추적 프레임 수": len(points)
                    }
                )

            if movement_rows:
                st.subheader("객체별 이동 방향")

                st.dataframe(
                    movement_rows,
                    width="stretch",
                    hide_index=True
                )

            st.divider()
            st.subheader("⚠️ 사고 위험 장면 후보")

            if highest_risk_event is not None:
                risk_column_1, risk_column_2, risk_column_3 = (
                    st.columns(3)
                )

                risk_column_1.metric(
                    "최고 위험 점수",
                    f"{highest_risk_event['score']}점"
                )

                risk_column_2.metric(
                    "위험 단계",
                    highest_risk_event["level"]
                )

                risk_column_3.metric(
                    "발생 시간",
                    f"{highest_risk_event['time_seconds']}초"
                )

                st.write(
                    f"**관련 객체:** "
                    f"{highest_risk_event['first_class']} "
                    f"#{highest_risk_event['first_id']} / "
                    f"{highest_risk_event['second_class']} "
                    f"#{highest_risk_event['second_id']}"
                )

                st.write(
                    f"**경계 상자 겹침 정도:** "
                    f"{highest_risk_event['iou']}"
                )

                st.write(
                    f"**객체 사이 화면상 거리:** "
                    f"{highest_risk_event['pixel_gap']}픽셀"
                )

                approaching_text = (
                    "확인됨"
                    if highest_risk_event.get("approaching", False)
                    else "확인되지 않음"
                )

                st.write(
                    f"**서로 접근하는 움직임:** {approaching_text}"
                )

                st.write(
                    f"**화면상 거리 감소율:** "
                    f"{highest_risk_event.get('distance_decrease_percent', 0)}%"
                )

                if highest_risk_frame is not None:
                    risk_frame_rgb = cv2.cvtColor(
                        highest_risk_frame,
                        cv2.COLOR_BGR2RGB
                    )

                    st.image(
                        risk_frame_rgb,
                        caption=(
                            "객체의 접근 움직임, 화면상 거리와 겹침을 "
                            "기준으로 선택한 "
                            "최고 위험 장면 후보"
                        ),
                        width="stretch"
                    )

                st.warning(
                    "접근 움직임과 객체 경계 상자의 겹침은 원근감이나 "
                    "카메라 움직임 때문에 실제 충돌과 다르게 분석될 수 "
                    "있습니다. 검토가 필요한 장면 후보로 사용해주세요."
                )

            else:
                st.info(
                    "화면상 객체 거리 기준으로 위험 장면 후보가 "
                    "발견되지 않았습니다."
                )

            if last_frame is not None:
                last_frame_rgb = cv2.cvtColor(
                    last_frame,
                    cv2.COLOR_BGR2RGB
                )

                st.subheader("마지막 프레임 분석 결과")

                st.image(
                    last_frame_rgb,
                    caption="초록색 선: 객체가 이동한 화면상 경로",
                    width="stretch"
                )

            video_recommendation = recommend_accident_type(
                track_history,
                track_box_history,
                track_classes,
                width,
                height,
                frame_vehicle_history
            )

            recommendation_key = video_recommendation.get("rule_key")
            recommendation_confidence = video_recommendation.get(
                "confidence",
                0
            )

            video_rule_applied = (
                apply_video_recommendation
                and recommendation_key is not None
                and recommendation_confidence >= 60
            )

            if video_rule_applied:
                analysis_rule = get_fault_rule(
                    recommendation_key
                )
            else:
                analysis_rule = selected_rule

            st.divider()
            st.subheader("🤖 AI 영상 사고 유형 추천")

            recommendation_column_1, recommendation_column_2 = (
                st.columns(2)
            )

            recommendation_column_1.metric(
                "AI 추천 사고 유형",
                video_recommendation["title"]
            )

            recommendation_column_2.metric(
                "영상 분석 신뢰도",
                f"{recommendation_confidence}%"
            )

            st.write(
                f"**영상 판단 근거:** "
                f"{video_recommendation['reason']}"
            )

            if video_rule_applied:
                st.success(
                    f"영상 추천 결과를 적용하여 "
                    f"'{analysis_rule['name']}' 기준으로 "
                    "과실비율을 계산합니다."
                )
            elif not apply_video_recommendation:
                st.info(
                    "AI 영상 추천 자동 적용이 꺼져 있어 사용자가 "
                    "직접 선택한 사고 유형을 적용합니다."
                )
            else:
                st.info(
                    "영상 추천 신뢰도가 60%보다 낮아 사용자가 "
                    "직접 선택한 사고 유형을 적용합니다."
                )

            st.warning(
                "영상 추천은 객체의 화면상 이동과 크기 변화를 이용한 "
                "1차 추정입니다. 차선, 신호 및 충돌 전후 상황을 함께 "
                "확인해야 합니다."
            )

            base_fault_a = analysis_rule["fault_a"]
            base_fault_b = analysis_rule["fault_b"]

            adjusted_fault_a, adjusted_fault_b, applied_addition = (
                calculate_adjusted_fault(
                    base_fault_a,
                    base_fault_b,
                    modifier_target,
                    detected_modifiers
                )
            )

            st.divider()
            st.subheader("⚖️ 예상 과실비율 분석")

            fault_column_a, fault_column_b = st.columns(2)

            with fault_column_a:
                st.write("### 차량 A")
                st.write(analysis_rule["vehicle_a"])

                st.metric(
                    "예상 과실",
                    f"{adjusted_fault_a}%"
                )

                st.progress(adjusted_fault_a / 100)

                st.caption(
                    f"기본 과실비율: {base_fault_a}%"
                )

            with fault_column_b:
                st.write("### 차량 B")
                st.write(analysis_rule["vehicle_b"])

                st.metric(
                    "예상 과실",
                    f"{adjusted_fault_b}%"
                )

                st.progress(adjusted_fault_b / 100)

                st.caption(
                    f"기본 과실비율: {base_fault_b}%"
                )

            st.write(
                f"**적용 사고 유형:** {analysis_rule['name']}"
            )

            st.write(
                f"**공식 기준 도표:** {analysis_rule['chart']}"
            )

            st.write(
                f"**기본 판단 근거:** {analysis_rule['reason']}"
            )

            if applied_addition > 0:
                target_name = (
                    analysis_rule["vehicle_a"]
                    if modifier_target == "A"
                    else analysis_rule["vehicle_b"]
                )

                st.error(
                    f"{target_name}에 수정 요소 "
                    f"+{applied_addition}%를 적용했습니다."
                )

                st.write("**탐지된 수정 요소**")

                for modifier in detected_modifiers:
                    st.write(
                        f"- {modifier['name']}: "
                        f"{modifier['reason']}"
                    )

            elif detected_modifiers:
                st.info(
                    "수정 요소가 발견됐지만 적용할 차량을 선택하지 않아 "
                    "기본 과실비율만 표시했습니다."
                )

            else:
                st.info(
                    "사고 설명에서 별도의 수정 요소가 발견되지 않아 "
                    "기본 과실비율을 표시했습니다."
                )

            st.link_button(
                "손해보험협회 공식 기준 확인",
                analysis_rule["source_url"]
            )

            st.warning(
                "이 결과는 영상의 객체 이동과 입력된 설명을 함께 "
                "분석한 참고용 예상입니다. 실제 과실비율은 차선, 신호, "
                "속도 기록 등의 증거와 공식 판단에 따라 달라집니다."
            )

            st.subheader("사용자가 입력한 사고 상황")
            st.write(situation)

            with open(output_path, "rb") as result_file:
                st.download_button(
                    label="분석 영상 다운로드",
                    data=result_file.read(),
                    file_name="analyzed_video.mp4",
                    mime="video/mp4"
                )
