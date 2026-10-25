import math


VEHICLE_CLASSES = {"car", "bus", "truck", "motorcycle", "bicycle"}


def normalize_text(text):
    return (text or "").lower().replace(" ", "")


def contains_any(text, keywords):
    return any(keyword.replace(" ", "") in text for keyword in keywords)


def calculate_average(values):
    return sum(values) / len(values) if values else 0.0


def calculate_box_area(box):
    x1, y1, x2, y2 = box
    return max(0, x2 - x1) * max(0, y2 - y1)


def get_track_features(points, boxes, frame_width, frame_height):
    # 짧은 사고 영상과 추적 ID 변경을 고려해 3프레임부터 분석한다.
    if len(points) < 3:
        return None

    section_size = max(1, len(points) // 3)
    start_x = calculate_average([point[0] for point in points[:section_size]])
    start_y = calculate_average([point[1] for point in points[:section_size]])
    end_x = calculate_average([point[0] for point in points[-section_size:]])
    end_y = calculate_average([point[1] for point in points[-section_size:]])
    move_x = end_x - start_x
    move_y = end_y - start_y
    lateral_movement = abs(move_x) / max(frame_width, 1)
    vertical_movement = abs(move_y) / max(frame_height, 1)
    movement_distance = math.hypot(move_x, move_y)
    frame_diagonal = math.hypot(frame_width, frame_height)
    normalized_movement = movement_distance / max(frame_diagonal, 1)

    area_growth = 0.0
    start_area_ratio = 0.0
    end_area_ratio = 0.0
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
        frame_area = max(frame_width * frame_height, 1)
        start_area_ratio = start_area / frame_area
        end_area_ratio = end_area / frame_area

    center_zone_fraction = sum(
        0.22 <= point[0] / max(frame_width, 1) <= 0.78
        for point in points
    ) / len(points)

    return {
        "move_x": move_x,
        "move_y": move_y,
        "start_x_ratio": start_x / max(frame_width, 1),
        "end_x_ratio": end_x / max(frame_width, 1),
        "min_x_ratio": min(point[0] for point in points) / max(frame_width, 1),
        "max_x_ratio": max(point[0] for point in points) / max(frame_width, 1),
        "lateral_movement": lateral_movement,
        "vertical_movement": vertical_movement,
        "normalized_movement": normalized_movement,
        "area_growth": area_growth,
        "start_area_ratio": start_area_ratio,
        "end_area_ratio": end_area_ratio,
        "center_zone_fraction": center_zone_fraction,
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
    frame_area = max(frame_width * frame_height, 1)
    center_zone_fraction = sum(
        0.22 <= item["center_x"] / max(frame_width, 1) <= 0.78
        for item in observations
    ) / len(observations)

    return {
        "area_growth": area_growth,
        "start_area_ratio": start_area / frame_area,
        "end_area_ratio": end_area / frame_area,
        "center_zone_fraction": center_zone_fraction,
        "move_x": end_x - start_x,
        "move_y": end_y - start_y,
        "start_x_ratio": start_x / max(frame_width, 1),
        "end_x_ratio": end_x / max(frame_width, 1),
        "min_x_ratio": min(
            item["center_x"] for item in observations
        ) / max(frame_width, 1),
        "max_x_ratio": max(
            item["center_x"] for item in observations
        ) / max(frame_width, 1),
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


def _recommend_visual_candidate(
    track_history,
    track_box_history,
    track_classes,
    frame_width,
    frame_height,
    frame_vehicle_history=None,
    ego_motion=None,
    lane_analysis=None,
    situation=""
):
    lane_analysis = lane_analysis or {}
    ego_motion = ego_motion or {}
    normalized_situation = normalize_text(situation)
    rear_end_text_hint = contains_any(
        normalized_situation,
        (
            "앞차를추돌",
            "앞차와충돌",
            "앞차후미",
            "후방추돌",
            "뒤에서추돌",
        ),
    )
    skid_text_hint = contains_any(
        normalized_situation,
        ("미끄러져", "미끄러지", "빗길에밀려", "제동중밀려"),
    )
    intersection_text_hint = contains_any(
        normalized_situation,
        ("교차로", "좌회전차", "소로", "대로직진", "측면에서진입"),
    )
    camera_unstable = (
        float(ego_motion.get("mean_absolute_shift", 0)) >= 0.004
        and float(ego_motion.get("consistency", 1)) < 0.62
    )
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

    has_lane_evidence = (
        lane_analysis.get("lane_change_detected", False)
        or lane_analysis.get("intersection_probability", 0) >= 60
    )
    if not vehicle_features and frame_features is None and not has_lane_evidence:
        return {
            "rule_key": None,
            "confidence": 0,
            "title": "영상 자동 추천 불가",
            "reason": "분석에 사용할 차량이 3프레임 이상 탐지되지 않았습니다."
        }

    candidates = []

    detected_vehicle_classes = set(track_classes.values())
    for frame_vehicles in frame_vehicle_history or []:
        for vehicle in frame_vehicles:
            detected_vehicle_classes.add(vehicle.get("class_name"))

    if (
        ego_motion.get("maneuver") == "u_turn"
        and ego_motion.get("confidence", 0) >= 65
    ):
        motorcycle_detected = "motorcycle" in detected_vehicle_classes
        candidates.append({
            "rule_key": (
                "uturn_vs_motorcycle"
                if motorcycle_detected
                else None
            ),
            "confidence": min(
                94,
                ego_motion.get("confidence", 0)
                + (2 if motorcycle_detected else 0)
            ),
            "title": (
                "유턴 자동차 대 이륜차 사고 가능성"
                if motorcycle_detected
                else "유턴 중 사고 가능성"
            ),
            "reason": (
                f"{ego_motion.get('reason', '')} "
                + (
                    "영상에서 이륜차도 함께 탐지됐습니다."
                    if motorcycle_detected
                    else "충돌 상대의 종류는 추가 확인이 필요합니다."
                )
            ).strip()
        })

    crossing_pairs = []
    vehicle_ids = list(vehicle_features.keys())
    for first_index in range(len(vehicle_ids)):
        for second_index in range(first_index + 1, len(vehicle_ids)):
            first_id = vehicle_ids[first_index]
            second_id = vehicle_ids[second_index]
            first_features = vehicle_features[first_id]
            second_features = vehicle_features[second_id]
            if (
                first_features["normalized_movement"] < 0.035
                or second_features["normalized_movement"] < 0.035
            ):
                continue
            similarity = calculate_direction_similarity(
                first_features,
                second_features,
            )
            if abs(similarity) <= 0.45:
                crossing_pairs.append((first_id, second_id, similarity))

    intersection_road_evidence = (
        lane_analysis.get("intersection_probability", 0) >= 60
        and lane_analysis.get("confidence", 0) >= 45
    )
    intersection_allowed = bool(crossing_pairs) and (
        intersection_road_evidence or intersection_text_hint
    )

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
        crosses_center_zone = (
            features["min_x_ratio"] <= 0.58
            and features["max_x_ratio"] >= 0.42
        )
        strong_side_motion = (
            lateral >= 0.06
            and horizontal_dominant
            and area_growth >= 0.12
            and (crosses_center_zone or side_entry)
        )
        crossing_from_side = (
            strong_side_motion
            and (
                features["tracked_frames"] <= 30
                or lateral >= 0.12
            )
        )

        # 단일 차량의 좌우 이동은 카메라 흔들림이나 미끄러짐일 수 있다.
        # 도로 구조와 서로 다른 두 차량의 교차 진행이 함께 확인될 때만
        # 교차로 사고 후보로 사용한다.
        if crossing_from_side and intersection_allowed:
            candidates.append({
                "rule_key": "intersection",
                "confidence": min(
                    92,
                    int(
                        72
                        + lateral * 85
                        + min(max(area_growth, 0) * 7, 9)
                        + (3 if toward_center else 0)
                    )
                ),
                "title": "교차로 측면 충돌 가능성",
                "reason": (
                    f"{features['class_name']} #{track_id}가 화면 중앙 통과 "
                    "영역에서 좌우 방향으로 빠르게 이동했습니다. "
                    "차량 크기 증가보다 좌우 교차 움직임을 우선 적용했습니다."
                )
            })

        central_front_vehicle = (
            features["center_zone_fraction"] >= 0.60
            and 0.20 <= end_x_ratio <= 0.80
        )
        approaching_front_vehicle = (
            area_growth >= 0.18
            or (
                area_growth >= 0.10
                and features["end_area_ratio"] >= 0.055
            )
        )
        lateral_explained_by_ego = (
            lateral < 0.10
            or (
                lateral < 0.30
                and (camera_unstable or skid_text_hint or rear_end_text_hint)
            )
        )

        if (
            approaching_front_vehicle
            and central_front_vehicle
            and lateral_explained_by_ego
            and features["move_y"] > -frame_height * 0.04
            and not intersection_allowed
        ):
            confidence = min(
                90,
                int(
                    48
                    + max(area_growth, 0) * 32
                    + features["center_zone_fraction"] * 12
                    + min(features["tracked_frames"], 10)
                    + (8 if rear_end_text_hint else 0)
                    + (3 if skid_text_hint else 0)
                )
            )
            candidates.append({
                "rule_key": "rear_end",
                "confidence": confidence,
                "title": "주행 중 후방 추돌 가능성",
                "reason": (
                    f"{features['class_name']} #{track_id}의 화면상 크기가 "
                    f"약 {area_growth * 100:.1f}% 커졌고, 전체 추적 구간의 "
                    f"{features['center_zone_fraction'] * 100:.0f}%에서 앞쪽 "
                    "중앙 영역에 있었습니다. "
                    + (
                        "좌우 흔들림은 블랙박스 차량의 불안정한 움직임과 "
                        "사고 설명을 함께 고려했습니다."
                        if lateral >= 0.10
                        else "좌우 이동은 비교적 작았습니다."
                    )
                )
            })

        if (
            lateral >= 0.12
            and not crossing_from_side
            and not intersection_allowed
            and (
                not camera_unstable
                or lane_analysis.get("lane_change_detected", False)
            )
        ):
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

        if (
            0.08 <= lateral < 0.20
            and area_growth >= 0.15
            and not crossing_from_side
            and not camera_unstable
            and not intersection_allowed
        ):
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

    if intersection_allowed:
        first_id, second_id, _ = crossing_pairs[0]
        candidates.append({
            "rule_key": "intersection",
            "confidence": min(
                88,
                int(
                    61
                    + lane_analysis.get("intersection_probability", 0) * 0.16
                    + lane_analysis.get("confidence", 0) * 0.12
                    + (5 if intersection_text_hint else 0)
                ),
            ),
            "title": "교차로 교차 진행 사고 가능성",
            "reason": (
                f"차량 #{first_id}와 차량 #{second_id}의 진행 방향이 서로 "
                "교차했고 교차로 도로 구조 또는 사고 설명이 함께 확인됐습니다."
            ),
        })

    # 추적 번호가 짧게 끊긴 경우에만 프레임별 대표 차량 변화로 보완한다.
    # 정상 추적 결과가 충분한데 대표 차량을 다시 고르면 서로 다른 차량을
    # 한 차량처럼 이어 붙일 수 있으므로 보완 분석의 사용 범위를 제한한다.
    longest_track = max(
        (
            features["tracked_frames"]
            for features in vehicle_features.values()
        ),
        default=0
    )
    tracking_is_fragmented = longest_track <= 6

    if frame_features is not None and (not candidates or tracking_is_fragmented):
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
        crosses_center_zone = (
            frame_features["min_x_ratio"] <= 0.58
            and frame_features["max_x_ratio"] >= 0.42
        )
        strong_side_motion = (
            lateral >= 0.06
            and horizontal_dominant
            and area_growth >= 0.12
            and (crosses_center_zone or side_entry)
        )
        crossing_from_side = (
            strong_side_motion
            and (observed_frames <= 30 or lateral >= 0.12)
        )

        if crossing_from_side and intersection_allowed:
            candidates.append({
                "rule_key": "intersection",
                "confidence": min(
                    88,
                    int(
                        70
                        + lateral * 80
                        + min(max(area_growth, 0) * 7, 8)
                        + (2 if toward_center else 0)
                    )
                ),
                "title": "교차로 측면 충돌 가능성",
                "reason": (
                    "추적 번호가 끊긴 구간을 포함해 분석한 결과, 대표 차량이 "
                    "화면 중앙 통과 영역에서 좌우 방향으로 이동했습니다."
                )
            })

        central_front_vehicle = (
            frame_features["center_zone_fraction"] >= 0.60
            and 0.20 <= end_x_ratio <= 0.80
        )
        approaching_front_vehicle = (
            area_growth >= 0.18
            or (
                area_growth >= 0.10
                and frame_features["end_area_ratio"] >= 0.055
            )
        )
        lateral_explained_by_ego = (
            lateral < 0.10
            or (
                lateral < 0.30
                and (camera_unstable or skid_text_hint or rear_end_text_hint)
            )
        )

        if (
            approaching_front_vehicle
            and central_front_vehicle
            and lateral_explained_by_ego
            and frame_features["move_y"] > -frame_height * 0.04
            and not intersection_allowed
        ):
            candidates.append({
                "rule_key": "rear_end",
                "confidence": min(
                    84,
                    int(
                        47
                        + max(area_growth, 0) * 32
                        + frame_features["center_zone_fraction"] * 12
                        + min(observed_frames, 10)
                        + (8 if rear_end_text_hint else 0)
                        + (3 if skid_text_hint else 0)
                    )
                ),
                "title": "주행 중 후방 추돌 가능성",
                "reason": (
                    "추적 번호가 끊긴 구간을 포함한 대표 앞차의 크기가 "
                    f"약 {area_growth * 100:.1f}% 커졌고 화면 중앙에 "
                    "지속적으로 위치했습니다."
                )
            })

        if (
            lateral >= 0.12
            and not crossing_from_side
            and not camera_unstable
        ):
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

    lane_confidence = lane_analysis.get("confidence", 0)

    if (
        lane_analysis.get("lane_change_detected", False)
        and lane_confidence >= 50
    ):
        candidates.append({
            "rule_key": "lane_change",
            "confidence": min(88, max(62, lane_confidence)),
            "title": "차선 횡단을 동반한 진로 변경 가능성",
            "reason": (
                f"연속 프레임에서 차로 중심 상대 위치 변화가 "
                f"{lane_analysis.get('lane_crossing_count', 0)}회 확인됐습니다. "
                "단순한 객체 좌우 이동보다 차선 기하 증거를 함께 반영했습니다."
            ),
        })

    if (
        lane_analysis.get("intersection_probability", 0) >= 60
        and lane_confidence >= 45
        and intersection_allowed
    ):
        candidates.append({
            "rule_key": "intersection",
            "confidence": min(
                86,
                int(
                    lane_analysis.get("intersection_probability", 0) * 0.65
                    + lane_confidence * 0.35
                ),
            ),
            "title": "교차로·정지선 구간 사고 가능성",
            "reason": (
                "차선 분석에서 진행 방향과 수평인 노면선이 반복되어 "
                "교차로·정지선·횡단보도 구간 가능성이 확인됐습니다."
            ),
        })

    if not candidates:
        return {
            "rule_key": None,
            "confidence": 25,
            "title": "사고 유형을 확정하기 어려움",
            "reason": (
                "차량은 탐지됐지만 후방 접근, 차로 변경 또는 교차 진행 "
                "특징이 충분하지 않습니다."
            ),
            "decision_status": "hold",
            "alternatives": [],
        }

    candidates.sort(key=lambda item: item["confidence"], reverse=True)
    best_candidate = candidates[0]
    distinct_alternatives = []
    seen_rules = {best_candidate.get("rule_key")}
    for candidate in candidates[1:]:
        rule_key = candidate.get("rule_key")
        if rule_key in seen_rules:
            continue
        seen_rules.add(rule_key)
        distinct_alternatives.append({
            "rule_key": rule_key,
            "title": candidate["title"],
            "confidence": candidate["confidence"],
        })
        if len(distinct_alternatives) == 2:
            break

    if (
        distinct_alternatives
        and distinct_alternatives[0]["confidence"]
        >= best_candidate["confidence"] - 5
    ):
        return {
            "rule_key": None,
            "confidence": best_candidate["confidence"],
            "title": "사고 유형 추가 확인 필요",
            "reason": (
                f"'{best_candidate['title']}'과 "
                f"'{distinct_alternatives[0]['title']}'의 영상 증거가 "
                "비슷해 자동으로 하나를 확정하지 않았습니다."
            ),
            "decision_status": "hold",
            "alternatives": [
                {
                    "rule_key": best_candidate.get("rule_key"),
                    "title": best_candidate["title"],
                    "confidence": best_candidate["confidence"],
                },
                *distinct_alternatives,
            ],
            "analyzed_vehicle_count": max(
                len(vehicle_features),
                1 if frame_features is not None else 0,
            ),
        }

    best_candidate["decision_status"] = (
        "recommended" if best_candidate["confidence"] >= 60 else "hold"
    )
    best_candidate["alternatives"] = distinct_alternatives
    best_candidate["analyzed_vehicle_count"] = max(
        len(vehicle_features),
        1 if frame_features is not None else 0
    )
    return best_candidate


def recommend_accident_type(*args, **kwargs):
    """Separate an image-motion candidate from a supported fault-rule decision.

    Bounding-box growth does not identify the collision participant or prove
    same-direction travel. Text is an unverified premise, not visual evidence.
    """
    result = _recommend_visual_candidate(*args, **kwargs)
    situation = kwargs.get("situation", args[8] if len(args) > 8 else "")
    text = normalize_text(situation)
    crossing_description = (
        "직진" in text
        and contains_any(text, ("좌측에서", "왼쪽에서", "우측에서", "오른쪽에서", "교차", "측면에서"))
    )
    rear_description = contains_any(text, (
        "앞차를추돌", "앞차와충돌", "앞차후미", "후방추돌", "뒤에서추돌",
    ))
    reason = None
    code = None
    if crossing_description:
        code = "crossing_straight_requires_review"
        reason = (
            "입력 설명은 교차 방향 직진 차량의 충돌을 가리킵니다. "
            "이는 사용자가 제공한 정보이며 영상으로 확정한 사실은 아닙니다. "
            "현재 기준표에는 이 상황에 맞는 검증된 자동 판단 규칙이 없어 "
            "후방 추돌이나 대로 직진·소로 좌회전 비율을 대신 적용하지 않았습니다. "
            "충돌 상대, 각 차량의 신호, 진행 방향, 도로 폭과 진입 순서를 확인해야 합니다."
        )
    elif result.get("rule_key") == "intersection":
        code = "intersection_rule_preconditions_missing"
        reason = (
            "교차 진행 후보가 있지만 신호 없는 교차로의 대로 직진·소로 좌회전 "
            "사고라는 기준의 전제가 확인되지 않았습니다. 일반 교차로 사고에 "
            "특정 좌회전 사고 비율을 적용할 수 없어 판단을 보류했습니다."
        )
    elif result.get("rule_key") == "rear_end" and not rear_description:
        code = "collision_participant_unverified"
        reason = (
            "차량의 화면상 크기가 커지는 움직임은 탐지했지만, 그 차량이 실제 "
            "충돌 상대인지 또는 같은 방향의 앞차인지 확인하지 못했습니다. "
            "마주 오는 차량도 같은 특징을 보일 수 있어 후방 추돌 과실비율을 "
            "자동 적용하지 않았습니다. 충돌 전후 장면과 상대 차량의 진행 방향을 확인해 주세요."
        )
    if reason:
        return {
            "rule_key": None, "confidence": 0, "decision_status": "hold",
            "title": "사고 유형과 충돌 상대 확인 필요", "reason": reason,
            "hold_code": code, "visual_candidate": result,
            "analyzed_vehicle_count": result.get("analyzed_vehicle_count", 0),
            "alternatives": [],
        }
    if result.get("rule_key") == "rear_end":
        result["reason"] += " 후방 추돌이라는 입력 설명을 전제로 한 후보이며 충돌 상대를 영상으로 검증한 결과는 아닙니다."
        result["premise_source"] = "user_description_unverified"
    return result
