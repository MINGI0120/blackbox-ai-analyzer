import os
from collections import defaultdict, deque

import cv2
import numpy as np
import streamlit as st
from ultralytics import YOLO


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
    "블랙박스 영상과 사고 상황을 입력하면 "
    "AI가 객체의 종류와 이동 경로를 분석합니다."
)

st.warning(
    "분석 결과는 참고용 예상이며, 실제 과실비율은 "
    "보험사·경찰·법원의 판단에 따라 달라질 수 있습니다."
)

uploaded_video = st.file_uploader(
    "블랙박스 영상을 선택하세요",
    type=["mp4", "avi", "mov", "mkv"]
)

situation = st.text_area(
    "사고 상황을 입력하세요",
    placeholder="예: 회전교차로 안에서 주행 중 진입 차량과 충돌했습니다.",
    height=150
)

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
                object_name: 0 for object_name in target_objects
            }

            tracked_ids = set()
            track_history = defaultdict(lambda: deque(maxlen=60))
            track_classes = {}

            movement_threshold = max(width, height) * 0.02

            progress_bar = st.progress(0)
            status_text = st.empty()

            frame_number = 0
            last_frame = None

            with st.spinner("AI가 영상과 이동 경로를 분석하고 있습니다..."):
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
                        object_name: 0 for object_name in target_objects
                    }

                    if result.boxes is not None:
                        class_numbers = result.boxes.cls.int().cpu().tolist()

                        for class_number in class_numbers:
                            object_name = result.names[class_number]

                            if object_name in current_counts:
                                current_counts[object_name] += 1

                        if result.boxes.id is not None:
                            boxes = result.boxes.xywh.cpu().tolist()
                            track_ids = result.boxes.id.int().cpu().tolist()

                            for box, track_id, class_number in zip(
                                boxes,
                                track_ids,
                                class_numbers
                            ):
                                center_x = int(box[0])
                                center_y = int(box[1])
                                object_name = result.names[class_number]

                                tracked_ids.add(track_id)
                                track_classes[track_id] = object_name
                                track_history[track_id].append(
                                    (center_x, center_y)
                                )

                    for object_name, count in current_counts.items():
                        maximum_counts[object_name] = max(
                            maximum_counts[object_name],
                            count
                        )

                    analyzed_frame = result.plot()

                    # 객체가 지나온 경로를 초록색 선으로 표시
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

                    writer.write(analyzed_frame)
                    last_frame = analyzed_frame

                    frame_number += 1

                    if total_frames > 0:
                        progress = min(frame_number / total_frames, 1.0)
                        progress_bar.progress(progress)

                    status_text.write(
                        f"분석 중: {frame_number} / {total_frames} 프레임"
                    )

            video.release()
            writer.release()

            progress_bar.progress(1.0)
            status_text.success("영상 객체 및 이동 경로 분석이 완료되었습니다.")

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

            st.metric("추적된 객체 번호 수", len(tracked_ids))

            movement_rows = []

            for track_id in sorted(tracked_ids):
                points = track_history[track_id]

                movement_rows.append(
                    {
                        "객체 번호": track_id,
                        "객체 종류": track_classes.get(track_id, "unknown"),
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

            if last_frame is not None:
                last_frame_rgb = cv2.cvtColor(
                    last_frame,
                    cv2.COLOR_BGR2RGB
                )

                st.image(
                    last_frame_rgb,
                    caption="초록색 선: 객체가 이동한 화면상 경로",
                    width="stretch"
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

            st.info(
                "현재 이동 방향은 영상 화면의 픽셀 변화를 기준으로 계산됩니다. "
                "다음 단계에서 접근 속도 변화와 사고 위험 장면을 분석합니다."
            )