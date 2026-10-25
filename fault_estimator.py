import math


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def round_to_five(value):
    return int(round(value / 5.0) * 5)


def normalize_text(text):
    return (text or "").lower().replace(" ", "")


def contains_any(text, keywords):
    return any(keyword.replace(" ", "") in text for keyword in keywords)


def estimate_fault_ratio(
    rule_key,
    rule,
    situation,
    video_recommendation=None,
    ego_motion=None,
    highest_risk_event=None,
    lane_analysis=None,
    detected_modifiers=None,
    modifier_target=None,
):
    video_recommendation = video_recommendation or {}
    ego_motion = ego_motion or {}
    lane_analysis = lane_analysis or {}
    detected_modifiers = detected_modifiers or []
    text = normalize_text(situation)

    base_a = float(rule["fault_a"])
    score_a = base_a
    evidence = []
    unknowns = []
    confidence_parts = []
    conclusive_evidence = 0

    video_confidence = float(video_recommendation.get("confidence", 0))
    video_rule_key = video_recommendation.get("rule_key")

    if video_rule_key == rule_key and video_confidence > 0:
        confidence_parts.append(video_confidence)
        evidence.append({
            "name": "영상 사고 유형 일치",
            "effect": 0,
            "detail": (
                f"영상 분석이 같은 사고 유형을 {video_confidence:.0f}% "
                "신뢰도로 추천했습니다."
            ),
        })
    elif video_rule_key is not None and video_confidence >= 60:
        confidence_parts.append(max(20, 100 - video_confidence))
        unknowns.append("영상 추천 사고 유형과 적용 기준이 서로 다름")

    ego_confidence = float(ego_motion.get("confidence", 0))
    ego_maneuver = ego_motion.get("maneuver")
    uturn_rule = rule_key in {
        "uturn_vs_motorcycle",
        "signal_uturn_vs_motorcycle",
    }

    if uturn_rule:
        if ego_maneuver == "u_turn" and ego_confidence >= 60:
            confidence_parts.append(ego_confidence)
            evidence.append({
                "name": "영상에서 유턴 움직임 확인",
                "effect": 0,
                "detail": (
                    f"배경 흐름 분석에서 유턴 가능성이 "
                    f"{ego_confidence:.0f}%로 나타났습니다."
                ),
            })
        else:
            unknowns.append("영상에서 블랙박스 차량의 유턴 움직임이 충분히 확인되지 않음")

        signal_known = contains_any(
            text,
            ("상시유턴", "유턴신호", "신호에따라유턴", "불법유턴"),
        )
        if not signal_known:
            unknowns.append("유턴 허용 방식과 당시 신호 상태")

        if contains_any(
            text,
            ("불법유턴", "유턴금지", "유턴구역아님", "유턴구역을벗어"),
        ):
            score_a += 10
            evidence.append({
                "name": "허용되지 않은 유턴 가능성",
                "effect": 10,
                "detail": "유턴 차량의 통행 방해 책임을 높였습니다.",
            })

        if contains_any(
            text,
            ("유턴신호불이행", "방향지시등없이유턴", "깜빡이없이유턴"),
        ):
            score_a += 10
            evidence.append({
                "name": "유턴 신호 불이행",
                "effect": 10,
                "detail": "유턴 차량의 예측 가능성을 낮춘 요소를 반영했습니다.",
            })

        motorcycle_speeding = contains_any(
            text,
            (
                "오토바이과속",
                "이륜차과속",
                "오토바이가과속",
                "이륜차가과속",
            ),
        )
        if motorcycle_speeding:
            score_a -= 10
            evidence.append({
                "name": "상대 이륜차 과속",
                "effect": -10,
                "detail": "상대 이륜차가 사고 회피 가능성을 낮춘 요소를 반영했습니다.",
            })

        motorcycle_signal_violation = contains_any(
            text,
            (
                "오토바이신호위반",
                "오토바이가신호위반",
                "이륜차신호위반",
                "이륜차가신호위반",
                "적색신호직진",
            ),
        )
        protected_uturn = contains_any(
            text,
            ("유턴신호", "신호에따라유턴", "유턴신호에따라"),
        )
        if motorcycle_signal_violation:
            score_a -= 35
            conclusive_evidence += 1
            evidence.append({
                "name": "상대 이륜차 신호위반",
                "effect": -35,
                "detail": "상대 이륜차의 중대한 진행 위반을 반영했습니다.",
            })

        if protected_uturn and motorcycle_signal_violation:
            score_a -= 35
            conclusive_evidence += 1
            evidence.append({
                "name": "보호 유턴 신호 확인",
                "effect": -35,
                "detail": "정상 유턴 신호와 상대 신호위반이 함께 확인됐습니다.",
            })

    if rule_key == "rear_end":
        if contains_any(
            text,
            ("갑자기끼어들", "급차로변경", "끼어든직후", "진로변경직후"),
        ):
            score_a -= 25
            evidence.append({
                "name": "앞차의 급진로 변경",
                "effect": -25,
                "detail": "단순 후방 추돌과 다른 선행차 책임 요소를 반영했습니다.",
            })

        if contains_any(
            text,
            ("이유없이급정거", "고의급정거", "급정거직후"),
        ):
            score_a -= 15
            evidence.append({
                "name": "앞차의 비정상적인 급정거",
                "effect": -15,
                "detail": "피추돌 차량의 사고 기여 가능성을 반영했습니다.",
            })

        if not contains_any(text, ("정차중", "신호대기중", "주차중")):
            unknowns.append("앞차의 정차·급제동·진로 변경 여부")

    if rule_key in {"lane_change", "sudden_lane_change", "merge"}:
        if contains_any(
            text,
            ("방향지시등없이", "깜빡이없이", "갑자기차선변경"),
        ):
            if "vehicle_b" in rule and "진로변경" in rule["vehicle_b"]:
                score_a -= 10
            else:
                score_a += 10
            evidence.append({
                "name": "방향지시등 없는 급진로 변경",
                "effect": 10,
                "detail": "진로변경 차량의 예측 곤란성을 반영했습니다.",
            })

        lane_confidence = float(lane_analysis.get("confidence", 0))
        if (
            lane_analysis.get("lane_change_detected", False)
            and lane_confidence >= 50
        ):
            confidence_parts.append(lane_confidence)
            evidence.append({
                "name": "영상에서 차로 중심 상대 위치 변화 확인",
                "effect": 0,
                "detail": (
                    f"연속 프레임 차선 기하 분석에서 차로 중심 이동이 "
                    f"{lane_analysis.get('lane_crossing_count', 0)}회 "
                    "확인됐습니다. 책임 차량 식별이 아니라 사고 유형 "
                    "신뢰도에만 반영했습니다."
                ),
            })
            unknowns.append("차선을 변경한 차량과 정확한 충돌 위치")
        else:
            unknowns.append("차선 변경 시작 시점과 충돌 위치")

    if rule_key == "intersection":
        intersection_probability = float(
            lane_analysis.get("intersection_probability", 0)
        )
        lane_confidence = float(lane_analysis.get("confidence", 0))
        if intersection_probability >= 60 and lane_confidence >= 45:
            confidence_parts.append(
                min(lane_confidence, intersection_probability)
            )
            evidence.append({
                "name": "교차로형 노면 구조 확인",
                "effect": 0,
                "detail": (
                    "정지선·횡단보도처럼 진행 방향과 수평인 노면선이 "
                    "여러 프레임에서 확인됐습니다."
                ),
            })
        else:
            unknowns.append("교차로 구조와 충돌 지점")

    if detected_modifiers and modifier_target in {"A", "B"}:
        modifier_value = max(
            modifier["fault_addition"]
            for modifier in detected_modifiers
        )
        signed_effect = modifier_value if modifier_target == "A" else -modifier_value
        score_a += signed_effect
        target_name = rule["vehicle_a"] if modifier_target == "A" else rule["vehicle_b"]
        evidence.append({
            "name": "현저하거나 중대한 과실",
            "effect": signed_effect,
            "detail": (
                f"{target_name}에 탐지된 수정 요소 중 가장 큰 "
                f"{modifier_value}%를 반영했습니다."
            ),
        })
    elif detected_modifiers:
        unknowns.append("탐지된 위반 요소가 어느 차량에 해당하는지")

    if highest_risk_event is not None:
        risk_score = float(highest_risk_event.get("score", 0))
        if risk_score >= 60:
            confidence_parts.append(min(85, risk_score))
            evidence.append({
                "name": "충돌 위험 움직임 확인",
                "effect": 0,
                "detail": (
                    f"객체 접근 및 겹침 위험 점수가 {risk_score:.0f}점으로 "
                    "분석됐습니다. 이 값은 책임 방향이 아닌 충돌 가능성에만 사용했습니다."
                ),
            })

    if confidence_parts:
        mean_confidence = sum(confidence_parts) / len(confidence_parts)
    else:
        mean_confidence = 45.0

    confidence = mean_confidence - len(unknowns) * 7
    confidence = int(clamp(round(confidence), 20, 95))

    score_a = clamp(score_a, 0, 100)

    # 100:0은 높은 신뢰도와 복수의 결정적 증거가 함께 있을 때만 허용한다.
    allow_extreme = confidence >= 90 and conclusive_evidence >= 2
    if not allow_extreme:
        score_a = clamp(score_a, 5, 95)

    final_a = round_to_five(score_a)
    final_a = int(clamp(final_a, 0 if allow_extreme else 5, 100 if allow_extreme else 95))
    final_b = 100 - final_a

    uncertainty_width = 6 + len(unknowns) * 5 + max(0, 70 - confidence) * 0.15
    uncertainty_width = int(clamp(round_to_five(uncertainty_width), 5, 25))
    range_low_a = int(clamp(round_to_five(final_a - uncertainty_width), 0, 100))
    range_high_a = int(clamp(round_to_five(final_a + uncertainty_width), 0, 100))

    vehicle_a_name = rule["vehicle_a"]
    vehicle_b_name = rule["vehicle_b"]
    a_reasons = []
    b_reasons = []
    context_reasons = []

    if base_a > 50:
        a_reasons.append(
            f"적용한 공식 기준에서 {vehicle_a_name}의 기본 책임을 "
            f"{int(base_a)}%로 보고 있습니다. {rule['reason']}"
        )
    elif base_a < 50:
        b_reasons.append(
            f"적용한 공식 기준에서 {vehicle_b_name}의 기본 책임을 "
            f"{int(100 - base_a)}%로 보고 있습니다. {rule['reason']}"
        )
    else:
        context_reasons.append(
            f"공식 기준은 두 차량의 기본 책임을 동일하게 봅니다. "
            f"{rule['reason']}"
        )

    for item in evidence:
        if item["effect"] > 0:
            a_reasons.append(
                f"{item['name']}: {item['detail']} "
                f"차량 A 책임에 +{item['effect']}% 영향을 주었습니다."
            )
        elif item["effect"] < 0:
            b_reasons.append(
                f"{item['name']}: {item['detail']} "
                f"차량 A 책임을 {abs(item['effect'])}% 낮추는 방향으로 "
                "반영했습니다."
            )
        else:
            context_reasons.append(
                f"{item['name']}: {item['detail']}"
            )

    if final_a > final_b:
        headline = (
            f"{vehicle_a_name}의 책임이 더 큰 사고로 분석했습니다."
        )
    elif final_b > final_a:
        headline = (
            f"{vehicle_b_name}의 책임이 더 큰 사고로 분석했습니다."
        )
    else:
        headline = "두 차량의 책임이 비슷한 사고로 분석했습니다."

    maneuver_title = ego_motion.get("title")
    situation_summary = (
        f"영상과 입력 내용을 종합해 '{rule['name']}' 유형으로 분류했습니다."
    )
    if maneuver_title:
        situation_summary += (
            f" 블랙박스 차량의 움직임은 '{maneuver_title}'으로 "
            "분석됐습니다."
        )
    road_structure = lane_analysis.get("road_structure")
    if road_structure and road_structure != "판단 불가":
        situation_summary += (
            f" 차선·노면 분석에서는 '{road_structure}'로 판단했습니다."
        )

    ratio_change = final_a - int(base_a)
    if ratio_change > 0:
        ratio_change_summary = (
            f"공식 기준 시작값 {int(base_a)}:{int(100 - base_a)}에서 "
            f"차량 A 책임을 높이는 증거를 반영해 "
            f"{final_a}:{final_b}로 조정했습니다."
        )
    elif ratio_change < 0:
        ratio_change_summary = (
            f"공식 기준 시작값 {int(base_a)}:{int(100 - base_a)}에서 "
            f"차량 B 측 책임 요소를 반영해 {final_a}:{final_b}로 "
            "조정했습니다."
        )
    else:
        ratio_change_summary = (
            f"책임 비율을 바꿀 만큼 명확한 추가 증거가 없어 공식 기준 "
            f"시작값 {int(base_a)}:{int(100 - base_a)}을 유지했습니다."
        )

    if unknowns:
        uncertainty_summary = (
            f"{', '.join(unknowns)} 정보가 확인되지 않아 "
            f"차량 A {range_low_a}~{range_high_a}%, 차량 B "
            f"{100 - range_high_a}~{100 - range_low_a}% 범위로 봅니다."
        )
    else:
        uncertainty_summary = (
            "핵심 판단 정보가 비교적 충분해 예상 범위가 좁게 계산됐습니다."
        )

    return {
        "fault_a": final_a,
        "fault_b": final_b,
        "base_fault_a": int(base_a),
        "base_fault_b": int(100 - base_a),
        "range_low_a": range_low_a,
        "range_high_a": range_high_a,
        "range_low_b": 100 - range_high_a,
        "range_high_b": 100 - range_low_a,
        "confidence": confidence,
        "evidence": evidence,
        "unknowns": unknowns,
        "allow_extreme": allow_extreme,
        "calculation_method": "공식 기준 사전확률 + 영상·행동 증거 점수 융합",
        "headline": headline,
        "situation_summary": situation_summary,
        "ratio_change_summary": ratio_change_summary,
        "uncertainty_summary": uncertainty_summary,
        "a_reasons": a_reasons,
        "b_reasons": b_reasons,
        "context_reasons": context_reasons,
    }
