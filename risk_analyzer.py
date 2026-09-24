import math


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
    frame_height
):
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

            # 사람끼리 가까운 경우는 교통 충돌 후보에서 제외
            if (
                first_class == "person"
                and second_class == "person"
            ):
                continue

            # 두 객체 중 적어도 하나는 차량이어야 함
            if (
                first_class not in VEHICLE_CLASSES
                and second_class not in VEHICLE_CLASSES
            ):
                continue

            first_box = first["box"]
            second_box = second["box"]

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

            risk_score = 0

            # 화면에서 경계 상자가 겹치는 경우
            if iou > 0:
                risk_score = min(
                    100,
                    70 + int(iou * 150)
                )

            # 경계 상자가 매우 가까운 경우
            elif normalized_gap <= 0.02:
                risk_score = 65

            elif normalized_gap <= 0.05:
                risk_score = 50

            elif normalized_gap <= 0.08:
                risk_score = 40

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
                "pixel_gap": round(pixel_gap, 1)
            }

            if (
                highest_risk is None
                or risk_score > highest_risk["score"]
            ):
                highest_risk = risk_data

    return highest_risk