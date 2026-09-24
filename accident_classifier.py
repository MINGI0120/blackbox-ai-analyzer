import math


VEHICLE_CLASSES = {"car", "bus", "truck", "motorcycle"}


def calculate_average(values):
    return sum(values) / len(values) if values else 0.0


def calculate_box_area(box):
    x1, y1, x2, y2 = box
    return max(0, x2 - x1) * max(0, y2 - y1)


def get_track_features(points, boxes, frame_width, frame_height):
    # 짧은 사고 영상과 추적 ID 변경을 고려해 3프레임부터 분석한다.
    if len(points) < 3:
        return None

    start_x, start_y = points[0]
    end_x, end_y = points[-1]
    move_x = end_x - start_x
    move_y = end_y - start_y
    lateral_movement = abs(move_x) / max(frame_width, 1)
    vertical_movement = abs(move_y) / max(frame_height, 1)
    movement_distance = math.hypot(move_x, move_y)
    frame_diagonal = math.hypot(frame_width, frame_height)
    normalized_movement = movement_distance / max(frame_diagonal, 1)

    area_growth = 0.0
    if len(boxes) >= 3:
        section_size = max(1, len(boxes) // 3)
        start_area = calculate_average([
            calculate_box_area(box) for box in boxes[:section_size]
        ])
        end_area = calculate_average([
            calculate_box_area(box) for box in boxes[-section_size:]
        ])
        if start_area > 0:
            area_growth = (end_area - start_area) / start_area

    return {
        "move_x": move_x,
        "move_y": move_y,
        "start_x_ratio": start_x / max(frame_width, 1),
        "end_x_ratio": end_x / max(frame_width, 1),
        "lateral_movement": lateral_movement,
        "vertical_movement": vertical_movement,
        "normalized_movement": normalized_movement,
        "area_growth": area_growth,
        "tracked_frames": len(points)
    }


def get_frame_vehicle_features(
    frame_vehicle_history,
    frame_width,
    frame_height
):
    """추적 ID가 끊겨도 프레임별 대표 차량 변화를 계산한다."""
    observations = []

    for frame_index, vehicles in enumerate(frame_vehicle_history or []):
        valid_vehicles = [
            vehicle for vehicle in vehicles
            if vehicle.get("class_name") in VEHICLE_CLASSES
            and len(vehicle.get("box", [])) == 4
        ]
        if not valid_vehicles:
            continue

        representative = max(
            valid_vehicles,
            key=lambda vehicle: calculate_box_area(vehicle["box"])
        )
        x1, y1, x2, y2 = representative["box"]
        observations.append({
            "frame_index": frame_index,
            "class_name": representative["class_name"],
            "center_x": (x1 + x2) / 2,
            "center_y": (y1 + y2) / 2,
            "area": calculate_box_area(representative["box"])
        })

    if len(observations) < 3:
        return None

    section_size = max(1, len(observations) // 3)
    start_items = observations[:section_size]
    end_items = observations[-section_size:]
    start_area = calculate_average([item["area"] for item in start_items])
    end_area = calculate_average([item["area"] for item in end_items])
    area_growth = (
        (end_area - start_area) / start_area
        if start_area > 0 else 0.0
    )
    start_x = calculate_average([item["center_x"] for item in start_items])
    end_x = calculate_average([item["center_x"] for item in end_items])
    start_y = calculate_average([item["center_y"] for item in start_items])
    end_y = calculate_average([item["center_y"] for item in end_items])

    return {
        "area_growth": area_growth,
        "move_x": end_x - start_x,
        "move_y": end_y - start_y,
        "start_x_ratio": start_x / max(frame_width, 1),
        "end_x_ratio": end_x / max(frame_width, 1),
        "lateral_movement": abs(end_x - start_x) / max(frame_width, 1),
        "observed_frames": len(observations),
        "class_name": observations[-1]["class_name"]
    }


def calculate_direction_similarity(first_features, second_features):
    first_x = first_features["move_x"]
    first_y = first_features["move_y"]
    second_x = second_features["move_x"]
    second_y = second_features["move_y"]
    first_length = math.hypot(first_x, first_y)
    second_length = math.hypot(second_x, second_y)

    if first_length <= 0 or second_length <= 0:
        return 1.0

    return (
        first_x * second_x + first_y * second_y
    ) / (first_length * second_length)


def recommend_accident_type(
    track_history,
    track_box_history,
    track_classes,
    frame_width,
    frame_height,
    frame_vehicle_history=None
):
    vehicle_features = {}

    for track_id, points in track_history.items():
        object_class = track_classes.get(track_id, "unknown")
        if object_class not in VEHICLE_CLASSES:
            continue

        features = get_track_features(
            list(points),
            list(track_box_history.get(track_id, [])),
            frame_width,
            frame_height
        )
        if features is not None:
            features["class_name"] = object_class
            vehicle_features[track_id] = features

    frame_features = get_frame_vehicle_features(
        frame_vehicle_history,
        frame_width,
        frame_height
    )

    if not vehicle_features and frame_features is None:
        return {
            "rule_key": None,
            "confidence": 0,
            "title": "영상 자동 추천 불가",
            "reason": "분석에 사용할 차량이 3프레임 이상 탐지되지 않았습니다."
        }

    candidates = []

    for track_id, features in vehicle_features.items():
        area_growth = features["area_growth"]
        lateral = features["lateral_movement"]
        start_x_ratio = features["start_x_ratio"]
        end_x_ratio = features["end_x_ratio"]
        horizontal_dominant = (
            abs(features["move_x"]) > abs(features["move_y"]) * 1.25
        )
        side_entry = start_x_ratio <= 0.35 or start_x_ratio >= 0.65
        toward_center = (
            abs(end_x_ratio - 0.5) < abs(start_x_ratio - 0.5)
        )
        crossing_from_side = (
            features["tracked_frames"] <= 15
            and lateral >= 0.04
            and horizontal_dominant
            and side_entry
            and toward_center
            and area_growth >= 0.15
        )

        # 화면 옆에서 중앙으로 빠르게 가로지르는 차량은 후방 접근보다
        # 교차로 또는 측면 진입 사고 가능성을 우선한다.
        if crossing_from_side:
            candidates.append({
                "rule_key": "intersection",
                "confidence": min(
                    90,
                    int(70 + lateral * 80 + min(area_growth * 8, 10))
                ),
                "title": "교차로 측면 충돌 가능성",
                "reason": (
                    f"{features['class_name']} #{track_id}가 화면 옆에서 "
                    "중앙 방향으로 짧은 시간에 가로질러 진입했습니다. "
                    "차량 크기 증가보다 좌우 교차 움직임을 우선 적용했습니다."
                )
            })

        if (
            area_growth >= 0.20
            and lateral < 0.10
            and not crossing_from_side
        ):
            confidence = min(
                85,
                int(54 + area_growth * 35 + min(features["tracked_frames"], 10))
            )
            candidates.append({
                "rule_key": "rear_end",
                "confidence": confidence,
                "title": "주행 중 후방 추돌 가능성",
                "reason": (
                    f"{features['class_name']} #{track_id}의 화면상 크기가 "
                    f"약 {area_growth * 100:.1f}% 커지고 좌우 이동은 적었습니다."
                )
            })

        if lateral >= 0.12:
            confidence = min(82, int(50 + lateral * 100))
            rule_key = "lane_change"
            title = "일반적인 진로 변경 사고 가능성"
            if lateral >= 0.25 and features["tracked_frames"] <= 35:
                rule_key = "sudden_lane_change"
                title = "갑작스러운 진로 변경 가능성"
                confidence = min(88, confidence + 5)

            candidates.append({
                "rule_key": rule_key,
                "confidence": confidence,
                "title": title,
                "reason": (
                    f"{features['class_name']} #{track_id}의 좌우 이동량이 "
                    "크게 나타났습니다."
                )
            })

        if 0.08 <= lateral < 0.20 and area_growth >= 0.15:
            candidates.append({
                "rule_key": "merge",
                "confidence": min(
                    75,
                    int(50 + lateral * 70 + area_growth * 20)
                ),
                "title": "차로 감소 구간 합류 사고 가능성",
                "reason": (
                    f"{features['class_name']} #{track_id}가 옆 방향에서 "
                    "접근하는 움직임을 보였습니다."
                )
            })

    vehicle_ids = list(vehicle_features.keys())
    for first_index in range(len(vehicle_ids)):
        for second_index in range(first_index + 1, len(vehicle_ids)):
            first_id = vehicle_ids[first_index]
            second_id = vehicle_ids[second_index]
            first_features = vehicle_features[first_id]
            second_features = vehicle_features[second_id]
            if (
                first_features["normalized_movement"] < 0.05
                or second_features["normalized_movement"] < 0.05
            ):
                continue

            similarity = calculate_direction_similarity(
                first_features,
                second_features
            )
            if abs(similarity) <= 0.45:
                candidates.append({
                    "rule_key": "intersection",
                    "confidence": 65,
                    "title": "교차로 교차 진행 사고 가능성",
                    "reason": (
                        f"차량 #{first_id}와 차량 #{second_id}의 진행 방향이 "
                        "서로 교차하는 형태로 분석됐습니다."
                    )
                })

    # 추적 번호가 바뀐 구간은 프레임별 대표 차량 변화로 보완한다.
    if frame_features is not None:
        area_growth = frame_features["area_growth"]
        lateral = frame_features["lateral_movement"]
        observed_frames = frame_features["observed_frames"]
        start_x_ratio = frame_features["start_x_ratio"]
        end_x_ratio = frame_features["end_x_ratio"]
        horizontal_dominant = (
            abs(frame_features["move_x"])
            > abs(frame_features["move_y"]) * 1.25
        )
        side_entry = start_x_ratio <= 0.35 or start_x_ratio >= 0.65
        toward_center = (
            abs(end_x_ratio - 0.5) < abs(start_x_ratio - 0.5)
        )
        crossing_from_side = (
            observed_frames <= 15
            and lateral >= 0.04
            and horizontal_dominant
            and side_entry
            and toward_center
            and area_growth >= 0.15
        )

        if crossing_from_side:
            candidates.append({
                "rule_key": "intersection",
                "confidence": min(
                    86,
                    int(68 + lateral * 80 + min(area_growth * 8, 10))
                ),
                "title": "교차로 측면 충돌 가능성",
                "reason": (
                    "추적 번호가 끊긴 구간을 포함해 분석한 결과, 대표 차량이 "
                    "화면 옆에서 중앙으로 가로질러 진입했습니다."
                )
            })

        if (
            area_growth >= 0.20
            and lateral < 0.10
            and not crossing_from_side
        ):
            candidates.append({
                "rule_key": "rear_end",
                "confidence": min(
                    78,
                    int(54 + area_growth * 35 + min(observed_frames, 10))
                ),
                "title": "주행 중 후방 추돌 가능성",
                "reason": (
                    "추적 번호가 끊긴 구간을 포함한 대표 차량의 크기가 "
                    f"약 {area_growth * 100:.1f}% 커지고 좌우 이동은 적었습니다."
                )
            })

        if lateral >= 0.12:
            candidates.append({
                "rule_key": "lane_change",
                "confidence": min(
                    72,
                    int(50 + lateral * 90 + min(observed_frames, 8))
                ),
                "title": "일반적인 진로 변경 사고 가능성",
                "reason": (
                    "추적 번호가 끊긴 구간을 포함해 계산한 대표 차량의 "
                    "좌우 위치 변화가 크게 나타났습니다."
                )
            })

    if not candidates:
        return {
            "rule_key": None,
            "confidence": 25,
            "title": "사고 유형을 확정하기 어려움",
            "reason": (
                "차량은 탐지됐지만 후방 접근, 차로 변경 또는 교차 진행 "
                "특징이 충분하지 않습니다."
            )
        }

    best_candidate = max(candidates, key=lambda item: item["confidence"])
    best_candidate["analyzed_vehicle_count"] = max(
        len(vehicle_features),
        1 if frame_features is not None else 0
    )
    return best_candidate
