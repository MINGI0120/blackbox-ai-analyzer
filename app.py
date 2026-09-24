import os

import cv2
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


st.title("🚗 AI 블랙박스 사고 분석")
st.write("블랙박스 영상과 사고 상황을 입력하면 AI가 영상 속 객체를 분석합니다.")

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

            progress_bar = st.progress(0)
            status_text = st.empty()

            frame_number = 0
            last_frame = None

            with st.spinner("AI가 영상을 분석하고 있습니다..."):
                while True:
                    success, frame = video.read()

                    if not success:
                        break

                    result = model.predict(
                        source=frame,
                        device=0,
                        conf=0.35,
                        verbose=False
                    )[0]

                    current_counts = {
                        object_name: 0 for object_name in target_objects
                    }

                    if result.boxes is not None:
                        for class_number in result.boxes.cls.tolist():
                            object_name = result.names[int(class_number)]

                            if object_name in current_counts:
                                current_counts[object_name] += 1

                    for object_name, count in current_counts.items():
                        maximum_counts[object_name] = max(
                            maximum_counts[object_name],
                            count
                        )

                    analyzed_frame = result.plot()
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
            status_text.success("영상 객체 분석이 완료되었습니다.")

            st.subheader("AI 탐지 결과")

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

            if last_frame is not None:
                last_frame_rgb = cv2.cvtColor(
                    last_frame,
                    cv2.COLOR_BGR2RGB
                )

                st.image(
                    last_frame_rgb,
                    caption="마지막 프레임 객체 탐지 결과",
                    use_container_width=True
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
                "현재 단계에서는 차량과 사람 등을 탐지합니다. "
                "다음 단계에서 차량 이동 추적과 사고 상황 판정을 연결합니다."
            )