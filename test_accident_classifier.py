from collections import defaultdict

from accident_classifier import recommend_accident_type


FRAME_WIDTH = 1920
FRAME_HEIGHT = 1080


def make_box(center_x, center_y, width, height):
    return [
        center_x - width / 2,
        center_y - height / 2,
        center_x + width / 2,
        center_y + height / 2,
    ]


def test_skid_toward_front_car_is_rear_end_not_intersection():
    centers = [900, 970, 1060, 1140, 1080, 1000, 960, 980, 1010]
    sizes = [180, 195, 215, 240, 275, 315, 355, 400, 455]
    points = [(x, 560 + index * 12) for index, x in enumerate(centers)]
    boxes = [
        make_box(x, y, size, size * 0.62)
        for (x, y), size in zip(points, sizes)
    ]

    result = recommend_accident_type(
        track_history={7: points},
        track_box_history={7: boxes},
        track_classes={7: "car"},
        frame_width=FRAME_WIDTH,
        frame_height=FRAME_HEIGHT,
        ego_motion={
            "maneuver": "straight",
            "confidence": 55,
            "mean_absolute_shift": 0.009,
            "consistency": 0.48,
        },
        lane_analysis={
            "confidence": 60,
            "intersection_probability": 20,
            "lane_change_detected": False,
        },
        situation="주행 중 차량이 미끄러져 앞차를 추돌했습니다.",
    )

    assert result["rule_key"] == "rear_end"
    assert result["confidence"] >= 60


def test_intersection_requires_road_and_crossing_vehicle_evidence():
    first_points = [(260 + index * 115, 520) for index in range(9)]
    second_points = [(980, 240 + index * 65) for index in range(9)]
    first_boxes = [make_box(x, y, 220, 140) for x, y in first_points]
    second_boxes = [make_box(x, y, 190, 125) for x, y in second_points]

    result = recommend_accident_type(
        track_history={1: first_points, 2: second_points},
        track_box_history={1: first_boxes, 2: second_boxes},
        track_classes={1: "car", 2: "car"},
        frame_width=FRAME_WIDTH,
        frame_height=FRAME_HEIGHT,
        ego_motion={"maneuver": "straight", "confidence": 70},
        lane_analysis={
            "confidence": 72,
            "intersection_probability": 82,
            "lane_change_detected": False,
        },
        situation="교차로에서 두 차량이 충돌했습니다.",
    )

    assert result["rule_key"] is None
    assert result["hold_code"] == "intersection_rule_preconditions_missing"


def test_intersection_road_shape_alone_does_not_select_fault_rule():
    points = [(900 + index * 2, 520 + index * 2) for index in range(9)]
    boxes = [make_box(x, y, 180, 110) for x, y in points]

    result = recommend_accident_type(
        track_history={3: points},
        track_box_history={3: boxes},
        track_classes={3: "car"},
        frame_width=FRAME_WIDTH,
        frame_height=FRAME_HEIGHT,
        ego_motion={"maneuver": "straight", "confidence": 70},
        lane_analysis={
            "confidence": 80,
            "intersection_probability": 90,
            "lane_change_detected": False,
        },
        situation="충돌 장면입니다.",
    )

    assert result["rule_key"] is None
    assert result["decision_status"] == "hold"


def test_ambiguous_video_is_held_instead_of_using_default_rule():
    result = recommend_accident_type(
        track_history=defaultdict(list),
        track_box_history=defaultdict(list),
        track_classes={},
        frame_width=FRAME_WIDTH,
        frame_height=FRAME_HEIGHT,
        ego_motion={"maneuver": "unknown", "confidence": 0},
        lane_analysis={},
        situation="사고가 발생했습니다.",
    )

    assert result["rule_key"] is None


def test_approaching_vehicle_without_collision_identity_is_held():
    points = [(960, 500 + i * 10) for i in range(12)]
    boxes = [make_box(x, y, 150 + i * 30, 100 + i * 20) for i, (x, y) in enumerate(points)]
    result = recommend_accident_type({1: points}, {1: boxes}, {1: "car"}, 1920, 1080)
    assert result["rule_key"] is None
    assert result["hold_code"] == "collision_participant_unverified"


def test_crossing_description_is_not_treated_as_visual_proof():
    points = [(960, 500 + i * 10) for i in range(12)]
    boxes = [make_box(x, y, 150 + i * 30, 100 + i * 20) for i, (x, y) in enumerate(points)]
    result = recommend_accident_type({1: points}, {1: boxes}, {1: "car"}, 1920, 1080,
                                     situation="직진 중 좌측에서 직진하는 차량과 충돌")
    assert result["rule_key"] is None
    assert result["hold_code"] == "crossing_straight_requires_review"
    assert "사용자가 제공한 정보" in result["reason"]
