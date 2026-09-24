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
    page_title="AI 釉붾옓諛뺤뒪 ?ш퀬 遺꾩꽍",
    page_icon="?슅",
    layout="wide"
)


@st.cache_resource
def load_model():
    return YOLO("yolo11n.pt")


def get_direction(points, movement_threshold):
    if len(points) < 2:
        return "?먮떒 遺덇?"

    start_x, start_y = points[0]
    end_x, end_y = points[-1]

    move_x = end_x - start_x
    move_y = end_y - start_y

    if abs(move_x) < movement_threshold and abs(move_y) < movement_threshold:
        return "?吏곸엫 ?곸쓬"

    if abs(move_x) > abs(move_y):
        if move_x > 0:
            return "?붾㈃ ?ㅻⅨ履쎌쑝濡??대룞"

        return "?붾㈃ ?쇱そ?쇰줈 ?대룞"

    if move_y > 0:
        return "?붾㈃ ?꾨옒履쎌쑝濡??대룞"

    return "?붾㈃ ?꾩そ?쇰줈 ?대룞"


st.title("?슅 AI 釉붾옓諛뺤뒪 ?ш퀬 遺꾩꽍")

st.write(
    "釉붾옓諛뺤뒪 ?곸긽怨??ш퀬 ?곹솴???낅젰?섎㈃ AI媛 媛앹껜??醫낅쪟, "
    "?대룞 寃쎈줈, ?꾪뿕 ?λ㈃ 諛??덉긽 怨쇱떎鍮꾩쑉??遺꾩꽍?⑸땲??"
)

st.warning(
    "遺꾩꽍 寃곌낵??李멸퀬???덉긽?대ŉ, ?ㅼ젣 怨쇱떎鍮꾩쑉? ?ш퀬 ?뱀떆???좏샇, "
    "?띾룄, ?꾨줈 ?곹깭? 蹂댄뿕??룰꼍李걔룸쾿?먯쓽 ?먮떒???곕씪 ?щ씪吏????덉뒿?덈떎."
)

rule_options = get_rule_options()

selected_rule_name = st.selectbox(
    "吏곸젒 ?좏깮 ?먮뒗 AI 異붿쿇 ?ㅽ뙣 ???ъ슜???ш퀬 ?좏삎",
    options=list(rule_options.keys()),
    help=(
        "AI ?곸긽 異붿쿇???좊ː?꾧? ??굅???먮룞 ?곸슜????寃쎌슦 "
        "???ш퀬 ?좏삎???ъ슜?⑸땲??"
    )
)

selected_rule_key = rule_options[selected_rule_name]
selected_rule = get_fault_rule(selected_rule_key)

apply_video_recommendation = st.checkbox(
    "AI媛 ?곸긽?먯꽌 異붿쿇???ш퀬 ?좏삎??怨쇱떎鍮꾩쑉 怨꾩궛???곸슜",
    value=True,
    help=(
        "?곸긽 異붿쿇 ?좊ː?꾧? 60% ?댁긽???뚮쭔 ?먮룞?쇰줈 ?곸슜?섎ŉ, "
        "洹몃낫????쑝硫?吏곸젒 ?좏깮???ш퀬 ?좏삎???ъ슜?⑸땲??"
    )
)

with st.expander("?좏깮???ш퀬 ?좏삎??湲곗? 蹂닿린"):
    st.write(f"**怨듭떇 湲곗? ?꾪몴:** {selected_rule['chart']}")
    st.write(f"**李⑤웾 A:** {selected_rule['vehicle_a']}")
    st.write(f"**李⑤웾 B:** {selected_rule['vehicle_b']}")
    st.write(
        f"**湲곕낯 怨쇱떎鍮꾩쑉:** "
        f"{selected_rule['vehicle_a']} {selected_rule['fault_a']}% / "
        f"{selected_rule['vehicle_b']} {selected_rule['fault_b']}%"
    )

uploaded_video = st.file_uploader(
    "釉붾옓諛뺤뒪 ?곸긽???좏깮?섏꽭??,
    type=["mp4", "avi", "mov", "mkv"]
)

situation = st.text_area(
    "?ш퀬 ?곹솴???먯꽭???낅젰?섏꽭??,
    placeholder=(
        "?? ?곷? 李⑤웾???쒗븳?띾룄蹂대떎 20km ?댁긽 怨쇱냽?섎㈃??"
        "李⑤줈瑜?蹂寃쏀빐 異⑸룎?덉뒿?덈떎."
    ),
    height=150
)

detected_modifiers = detect_fault_modifiers(situation)
modifier_target = None

if detected_modifiers:
    st.subheader("?뵊 ?ш퀬 ?ㅻ챸?먯꽌 諛쒓껄???섏젙 ?붿냼")

    for modifier in detected_modifiers:
        st.warning(
            f"{modifier['name']} 쨌 {modifier['level']} 쨌 "
            f"理쒕? +{modifier['fault_addition']}%\n\n"
            f"{modifier['reason']}"
        )

    modifier_target_option = st.selectbox(
        "???섏젙 ?붿냼???대뒓 李⑤웾???대떦?⑸땲源?",
        options=[
            "?섏젙 ?붿냼瑜??곸슜?섏? ?딆쓬",
            "李⑤웾 A???곸슜",
            "李⑤웾 B???곸슜"
        ],
        help=(
            "?ш퀬 ?ㅻ챸留뚯쑝濡??꾨컲 李⑤웾???뺤젙?????놁쑝誘濡?"
            "利앷굅瑜??뺤씤?????좏깮?댁＜?몄슂."
        )
    )

    if modifier_target_option.startswith("李⑤웾 A"):
        modifier_target = "A"

    elif modifier_target_option.startswith("李⑤웾 B"):
        modifier_target = "B"

if uploaded_video is not None:
    st.subheader("?낅줈?쒗븳 ?곸긽")
    st.video(uploaded_video)

if st.button("AI ?ш퀬 遺꾩꽍 ?쒖옉", type="primary"):
    if uploaded_video is None:
        st.error("釉붾옓諛뺤뒪 ?곸긽??癒쇱? ?좏깮?댁＜?몄슂.")

    elif not situation.strip():
        st.error("?ш퀬 ?곹솴???낅젰?댁＜?몄슂.")

    else:
        os.makedirs("temp", exist_ok=True)

        input_path = os.path.join("temp", "uploaded_video.mp4")
        output_path = os.path.join("temp", "analyzed_video.mp4")

        with open(input_path, "wb") as file:
            file.write(uploaded_video.getbuffer())

        video = cv2.VideoCapture(input_path)

        if not video.isOpened():
            st.error("?곸긽??遺덈윭?ㅼ? 紐삵뻽?듬땲??")

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
                "AI媛 ?곸긽, ?대룞 寃쎈줈? ?꾪뿕 ?λ㈃??遺꾩꽍?섍퀬 ?덉뒿?덈떎..."
            ):
                while True:
                    success, frame = video.read()

                    if not success:
                        break

                    result = model.track(
                        source=frame,
                        
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

                        # 異붿쟻 踰덊샇媛 ?놁뼱???꾨젅?꾩뿉 ?섏삩 李⑤웾? 紐⑤몢 湲곕줉
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
                        f"遺꾩꽍 以? {frame_number} / "
                        f"{total_frames} ?꾨젅??
                    )

            video.release()
            writer.release()

            progress_bar.progress(1.0)

            status_text.success(
                "?곸긽 媛앹껜, ?대룞 寃쎈줈 諛??꾪뿕 ?λ㈃ 遺꾩꽍???꾨즺?섏뿀?듬땲??"
            )

            st.subheader("AI ?먯? 諛?異붿쟻 寃곌낵")

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
                st.info("二쇱슂 ?꾨줈 媛앹껜媛 ?먯??섏? ?딆븯?듬땲??")

            st.metric(
                "異붿쟻??媛앹껜 踰덊샇 ??,
                len(tracked_ids)
            )

            movement_rows = []

            for track_id in sorted(tracked_ids):
                points = track_history[track_id]

                movement_rows.append(
                    {
                        "媛앹껜 踰덊샇": track_id,
                        "媛앹껜 醫낅쪟": track_classes.get(
                            track_id,
                            "unknown"
                        ),
                        "?대룞 諛⑺뼢": get_direction(
                            points,
                            movement_threshold
                        ),
                        "異붿쟻 ?꾨젅????: len(points)
                    }
                )

            if movement_rows:
                st.subheader("媛앹껜蹂??대룞 諛⑺뼢")

                st.dataframe(
                    movement_rows,
                    width="stretch",
                    hide_index=True
                )

            st.divider()
            st.subheader("?좑툘 ?ш퀬 ?꾪뿕 ?λ㈃ ?꾨낫")

            if highest_risk_event is not None:
                risk_column_1, risk_column_2, risk_column_3 = (
                    st.columns(3)
                )

                risk_column_1.metric(
                    "理쒓퀬 ?꾪뿕 ?먯닔",
                    f"{highest_risk_event['score']}??
                )

                risk_column_2.metric(
                    "?꾪뿕 ?④퀎",
                    highest_risk_event["level"]
                )

                risk_column_3.metric(
                    "諛쒖깮 ?쒓컙",
                    f"{highest_risk_event['time_seconds']}珥?
                )

                st.write(
                    f"**愿??媛앹껜:** "
                    f"{highest_risk_event['first_class']} "
                    f"#{highest_risk_event['first_id']} / "
                    f"{highest_risk_event['second_class']} "
                    f"#{highest_risk_event['second_id']}"
                )

                st.write(
                    f"**寃쎄퀎 ?곸옄 寃뱀묠 ?뺣룄:** "
                    f"{highest_risk_event['iou']}"
                )

                st.write(
                    f"**媛앹껜 ?ъ씠 ?붾㈃??嫄곕━:** "
                    f"{highest_risk_event['pixel_gap']}?쎌?"
                )

                approaching_text = (
                    "?뺤씤??
                    if highest_risk_event.get("approaching", False)
                    else "?뺤씤?섏? ?딆쓬"
                )

                st.write(
                    f"**?쒕줈 ?묎렐?섎뒗 ?吏곸엫:** {approaching_text}"
                )

                st.write(
                    f"**?붾㈃??嫄곕━ 媛먯냼??** "
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
                            "媛앹껜???묎렐 ?吏곸엫, ?붾㈃??嫄곕━? 寃뱀묠??"
                            "湲곗??쇰줈 ?좏깮??"
                            "理쒓퀬 ?꾪뿕 ?λ㈃ ?꾨낫"
                        ),
                        width="stretch"
                    )

                st.warning(
                    "?묎렐 ?吏곸엫怨?媛앹껜 寃쎄퀎 ?곸옄??寃뱀묠? ?먭렐媛먯씠??"
                    "移대찓???吏곸엫 ?뚮Ц???ㅼ젣 異⑸룎怨??ㅻⅤ寃?遺꾩꽍????"
                    "?덉뒿?덈떎. 寃?좉? ?꾩슂???λ㈃ ?꾨낫濡??ъ슜?댁＜?몄슂."
                )

            else:
                st.info(
                    "?붾㈃??媛앹껜 嫄곕━ 湲곗??쇰줈 ?꾪뿕 ?λ㈃ ?꾨낫媛 "
                    "諛쒓껄?섏? ?딆븯?듬땲??"
                )

            if last_frame is not None:
                last_frame_rgb = cv2.cvtColor(
                    last_frame,
                    cv2.COLOR_BGR2RGB
                )

                st.subheader("留덉?留??꾨젅??遺꾩꽍 寃곌낵")

                st.image(
                    last_frame_rgb,
                    caption="珥덈줉???? 媛앹껜媛 ?대룞???붾㈃??寃쎈줈",
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
            st.subheader("?쨼 AI ?곸긽 ?ш퀬 ?좏삎 異붿쿇")

            recommendation_column_1, recommendation_column_2 = (
                st.columns(2)
            )

            recommendation_column_1.metric(
                "AI 異붿쿇 ?ш퀬 ?좏삎",
                video_recommendation["title"]
            )

            recommendation_column_2.metric(
                "?곸긽 遺꾩꽍 ?좊ː??,
                f"{recommendation_confidence}%"
            )

            st.write(
                f"**?곸긽 ?먮떒 洹쇨굅:** "
                f"{video_recommendation['reason']}"
            )

            if video_rule_applied:
                st.success(
                    f"?곸긽 異붿쿇 寃곌낵瑜??곸슜?섏뿬 "
                    f"'{analysis_rule['name']}' 湲곗??쇰줈 "
                    "怨쇱떎鍮꾩쑉??怨꾩궛?⑸땲??"
                )
            elif not apply_video_recommendation:
                st.info(
                    "AI ?곸긽 異붿쿇 ?먮룞 ?곸슜??爰쇱졇 ?덉뼱 ?ъ슜?먭? "
                    "吏곸젒 ?좏깮???ш퀬 ?좏삎???곸슜?⑸땲??"
                )
            else:
                st.info(
                    "?곸긽 異붿쿇 ?좊ː?꾧? 60%蹂대떎 ??븘 ?ъ슜?먭? "
                    "吏곸젒 ?좏깮???ш퀬 ?좏삎???곸슜?⑸땲??"
                )

            st.warning(
                "?곸긽 異붿쿇? 媛앹껜???붾㈃???대룞怨??ш린 蹂?붾? ?댁슜??"
                "1李?異붿젙?낅땲?? 李⑥꽑, ?좏샇 諛?異⑸룎 ?꾪썑 ?곹솴???④퍡 "
                "?뺤씤?댁빞 ?⑸땲??"
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
            st.subheader("?뽳툘 ?덉긽 怨쇱떎鍮꾩쑉 遺꾩꽍")

            fault_column_a, fault_column_b = st.columns(2)

            with fault_column_a:
                st.write("### 李⑤웾 A")
                st.write(analysis_rule["vehicle_a"])

                st.metric(
                    "?덉긽 怨쇱떎",
                    f"{adjusted_fault_a}%"
                )

                st.progress(adjusted_fault_a / 100)

                st.caption(
                    f"湲곕낯 怨쇱떎鍮꾩쑉: {base_fault_a}%"
                )

            with fault_column_b:
                st.write("### 李⑤웾 B")
                st.write(analysis_rule["vehicle_b"])

                st.metric(
                    "?덉긽 怨쇱떎",
                    f"{adjusted_fault_b}%"
                )

                st.progress(adjusted_fault_b / 100)

                st.caption(
                    f"湲곕낯 怨쇱떎鍮꾩쑉: {base_fault_b}%"
                )

            st.write(
                f"**?곸슜 ?ш퀬 ?좏삎:** {analysis_rule['name']}"
            )

            st.write(
                f"**怨듭떇 湲곗? ?꾪몴:** {analysis_rule['chart']}"
            )

            st.write(
                f"**湲곕낯 ?먮떒 洹쇨굅:** {analysis_rule['reason']}"
            )

            if applied_addition > 0:
                target_name = (
                    analysis_rule["vehicle_a"]
                    if modifier_target == "A"
                    else analysis_rule["vehicle_b"]
                )

                st.error(
                    f"{target_name}???섏젙 ?붿냼 "
                    f"+{applied_addition}%瑜??곸슜?덉뒿?덈떎."
                )

                st.write("**?먯????섏젙 ?붿냼**")

                for modifier in detected_modifiers:
                    st.write(
                        f"- {modifier['name']}: "
                        f"{modifier['reason']}"
                    )

            elif detected_modifiers:
                st.info(
                    "?섏젙 ?붿냼媛 諛쒓껄?먯?留??곸슜??李⑤웾???좏깮?섏? ?딆븘 "
                    "湲곕낯 怨쇱떎鍮꾩쑉留??쒖떆?덉뒿?덈떎."
                )

            else:
                st.info(
                    "?ш퀬 ?ㅻ챸?먯꽌 蹂꾨룄???섏젙 ?붿냼媛 諛쒓껄?섏? ?딆븘 "
                    "湲곕낯 怨쇱떎鍮꾩쑉???쒖떆?덉뒿?덈떎."
                )

            st.link_button(
                "?먰빐蹂댄뿕?묓쉶 怨듭떇 湲곗? ?뺤씤",
                analysis_rule["source_url"]
            )

            st.warning(
                "??寃곌낵???곸긽??媛앹껜 ?대룞怨??낅젰???ㅻ챸???④퍡 "
                "遺꾩꽍??李멸퀬???덉긽?낅땲?? ?ㅼ젣 怨쇱떎鍮꾩쑉? 李⑥꽑, ?좏샇, "
                "?띾룄 湲곕줉 ?깆쓽 利앷굅? 怨듭떇 ?먮떒???곕씪 ?щ씪吏묐땲??"
            )

            st.subheader("?ъ슜?먭? ?낅젰???ш퀬 ?곹솴")
            st.write(situation)

            with open(output_path, "rb") as result_file:
                st.download_button(
                    label="遺꾩꽍 ?곸긽 ?ㅼ슫濡쒕뱶",
                    data=result_file.read(),
                    file_name="analyzed_video.mp4",
                    mime="video/mp4"
                )

