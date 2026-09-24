import math
from collections import deque


ROAD_USER_CLASSES = {
    "person",
    "car",
    "bus",
    "truck",
    "motorcycle",
    "bicycle"
}

VEHICLE_CLASSES = {
    "car",
    "bus",
    "truck",
    "motorcycle",
    "bicycle"
}


def calculate_iou(box_a, box_b):
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    intersection_x1 = max(ax1, bx1)
    intersection_y1 = max(ay1, by1)
    intersection_x2 = min(ax2, bx2)
    intersection_y2 = min(ay2, by2)

    intersection_width = max(
        0,
        intersection_x2 - intersection_x1
    )

    intersection_height = max(
        0,
        intersection_y2 - intersection_y1
    )

    intersection_area = (
        intersection_width * intersection_height
    )

    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)

    union_area = area_a + area_b - intersection_area

    if union_area <= 0:
        return 0.0

    return intersection_area / union_area


def calculate_box_gap(box_a, box_b):
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    horizontal_gap = max(
        bx1 - ax2,
        ax1 - bx2,
        0
    )

    vertical_gap = max(
        by1 - ay2,
        ay1 - by2,
        0
    )

    return math.sqrt(
        horizontal_gap ** 2 + vertical_gap ** 2
    )


def calculate_bottom_center_distance(box_a, box_b):
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    first_x = (ax1 + ax2) / 2
    first_y = ay2

    second_x = (bx1 + bx2) / 2
    second_y = by2

    return math.sqrt(
        (first_x - second_x) ** 2
        + (first_y - second_y) ** 2
    )


def check_approaching(distance_history):
    if len(distance_history) < 6:
        return False, 0.0

    sample_size = max(
        2,
        len(distance_history) // 3
    )

    old_average = sum(
        list(distance_history)[:sample_size]
    ) / sample_size

    recent_average = sum(
        list(distance_history)[-sample_size:]
    ) / sample_size

    distance_decrease = old_average - recent_average

    if old_average <= 0:
        return False, 0.0

    decrease_ratio = distance_decrease / old_average

    approaching = (
        distance_decrease > 0.01
        and decrease_ratio >= 0.08
    )

    return approaching, max(0.0, decrease_ratio)


def get_risk_level(score):
    if score >= 80:
        return "높음"

    if score >= 60:
        return "주의"

    if score >= 40:
        return "관찰 필요"

    return "낮음"


def analyze_frame_risk(
    detections,
    frame_width,
    frame_height,
    pair_distance_history=None
):
    if pair_distance_history is None:
        pair_distance_history = {}

    frame_diagonal = math.sqrt(
        frame_width ** 2 + frame_height ** 2
    )

    road_users = [
        detection
        for detection in detections
        if detection["class_name"] in ROAD_USER_CLASSES
    ]

    highest_risk = None

    for first_index in range(len(road_users)):
        for second_index in range(
            first_index + 1,
            len(road_users)
        ):
            first = road_users[first_index]
            second = road_users[second_index]

            first_class = first["class_name"]
            second_class = second["class_name"]

            if (
                first_class == "person"
                and second_class == "person"
            ):
                continue

            if (
                first_class not in VEHICLE_CLASSES
                and second_class not in VEHICLE_CLASSES
            ):
                continue

            first_box = first["box"]
            second_box = second["box"]

            pair_key = tuple(
                sorted([
                    first["track_id"],
                    second["track_id"]
                ])
            )

            if pair_key not in pair_distance_history:
                pair_distance_history[pair_key] = deque(
                    maxlen=15
                )

            center_distance = calculate_bottom_center_distance(
                first_box,
                second_box
            )

            normalized_center_distance = (
                center_distance / frame_diagonal
                if frame_diagonal > 0
                else 1.0
            )

            pair_distance_history[pair_key].append(
                normalized_center_distance
            )

            approaching, decrease_ratio = check_approaching(
                pair_distance_history[pair_key]
            )

            iou = calculate_iou(
                first_box,
                second_box
            )

            pixel_gap = calculate_box_gap(
                first_box,
                second_box
            )

            normalized_gap = (
                pixel_gap / frame_diagonal
                if frame_diagonal > 0
                else 1.0
            )

            geometric_score = 0

            if iou > 0:
                geometric_score = min(
                    75,
                    55 + int(iou * 130)
                )

            elif normalized_gap <= 0.02:
                geometric_score = 55

            elif normalized_gap <= 0.05:
                geometric_score = 45

            elif normalized_gap <= 0.08:
                geometric_score = 35

            risk_score = geometric_score

            if approaching:
                approach_bonus = min(
                    35,
                    15 + int(decrease_ratio * 100)
                )

                risk_score = min(
                    100,
                    geometric_score + approach_bonus
                )

            else:
                # 가까워지는 움직임이 확인되지 않으면
                # 화면 겹침만으로 높은 위험 점수를 주지 않음
                risk_score = min(risk_score, 45)

            if risk_score < 40:
                continue

            risk_data = {
                "score": risk_score,
                "level": get_risk_level(risk_score),
                "first_id": first["track_id"],
                "first_class": first_class,
                "second_id": second["track_id"],
                "second_class": second_class,
                "iou": round(iou, 3),
                "pixel_gap": round(pixel_gap, 1),
                "approaching": approaching,
                "distance_decrease_percent": round(
                    decrease_ratio * 100,
                    1
                )
            }

            if (
                highest_risk is None
                or risk_score > highest_risk["score"]
            ):
                highest_risk = risk_data

    return highest_risk