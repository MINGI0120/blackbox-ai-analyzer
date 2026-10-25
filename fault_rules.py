FAULT_RULES = {
    "rear_end": {
        "name": "주행 중 후방 추돌",
        "chart": "차41-1",
        "vehicle_a": "뒤차(추돌차)",
        "vehicle_b": "앞차(피추돌차)",
        "fault_a": 100,
        "fault_b": 0,
        "reason": "뒤차의 전방주시 및 안전거리 확보 의무를 기준으로 한 기본 비율입니다.",
        "source_url": (
            "https://accident.knia.or.kr/myaccident-content"
            "?chartNo=%EC%B0%A841-1&chartType=1"
        ),
    },
    "lane_change": {
        "name": "일반적인 진로 변경 사고",
        "chart": "차43-2",
        "vehicle_a": "후행 직진차",
        "vehicle_b": "선행 진로변경차",
        "fault_a": 30,
        "fault_b": 70,
        "reason": "진로변경 차량의 안전한 차로 변경 의무를 더 크게 보는 기본 비율입니다.",
        "source_url": (
            "https://accident.knia.or.kr/myaccident-content"
            "?chartNo=%EC%B0%A843-2&chartType=1"
        ),
    },
    "sudden_lane_change": {
        "name": "정체 차로에서 갑작스러운 진로 변경",
        "chart": "차43-4",
        "vehicle_a": "진로변경차",
        "vehicle_b": "직진차",
        "fault_a": 100,
        "fault_b": 0,
        "reason": "정체 차로에서 갑자기 진로를 변경한 차량의 책임을 기준으로 합니다.",
        "source_url": (
            "https://accident.knia.or.kr/myaccident-content"
            "?chartNo=%EC%B0%A843-4&chartType=1"
        ),
    },
    "merge": {
        "name": "차로 감소 구간 합류 사고",
        "chart": "차43-1",
        "vehicle_a": "본선 진행차",
        "vehicle_b": "합류차",
        "fault_a": 40,
        "fault_b": 60,
        "reason": "차로가 감소하는 구간에서 합류차의 주의 의무를 더 크게 보는 기본 비율입니다.",
        "source_url": (
            "https://accident.knia.or.kr/myaccident-content"
            "?chartNo=%EC%B0%A843-1&chartType=1"
        ),
    },
    "intersection": {
        "name": "신호 없는 교차로 대로 직진 대 소로 좌회전",
        "chart": "차16-3",
        "vehicle_a": "대로 직진차",
        "vehicle_b": "소로 좌회전차",
        "fault_a": 20,
        "fault_b": 80,
        "reason": "폭이 넓은 도로의 직진차와 좁은 도로의 좌회전차가 충돌한 경우의 기본 비율입니다.",
        "source_url": (
            "https://accident.knia.or.kr/myaccident-content"
            "?chartNo=%EC%B0%A816-3&chartType=1"
        ),
    },
    "narrow_road": {
        "name": "좁은 도로 마주 오는 차량 간 사고",
        "chart": "차32-1",
        "vehicle_a": "맞은편 진행차 A",
        "vehicle_b": "맞은편 진행차 B",
        "fault_a": 50,
        "fault_b": 50,
        "reason": "좁은 도로에서 서로 마주 보며 진행한 차량의 기본 비율입니다.",
        "source_url": (
            "https://accident.knia.or.kr/myaccident-content"
            "?chartNo=%EC%B0%A832-1&chartType=1"
        ),
    },
    "uturn_vs_motorcycle": {
        "name": "상시유턴 자동차 대 맞은편 직진 이륜차",
        "chart": "이륜차 392 (가)",
        "vehicle_a": "유턴 자동차",
        "vehicle_b": "맞은편 직진 이륜차",
        "fault_a": 90,
        "fault_b": 10,
        "reason": (
            "상시유턴구역에서 자동차가 유턴하던 중 맞은편에서 직진하는 "
            "이륜차와 충돌한 경우의 기본 비율입니다."
        ),
        "source_url": (
            "https://accident.knia.or.kr/myaccident-content"
            "?chartNo=392&chartType=1"
        ),
    },
    "signal_uturn_vs_motorcycle": {
        "name": "신호유턴 자동차 대 신호위반 직진 이륜차",
        "chart": "이륜차 392 (나)",
        "vehicle_a": "신호에 따라 유턴한 자동차",
        "vehicle_b": "적색신호에 직진한 이륜차",
        "fault_a": 0,
        "fault_b": 100,
        "reason": (
            "자동차가 유턴 신호에 따라 유턴하고 맞은편 이륜차가 적색신호에 "
            "직진한 경우의 기본 비율입니다."
        ),
        "source_url": (
            "https://accident.knia.or.kr/myaccident-content"
            "?chartNo=392&chartType=1"
        ),
    },
}


def normalize_situation(situation):
    return (situation or "").lower().replace(" ", "")


def recommend_rule_from_situation(situation):
    text = normalize_situation(situation)
    has_uturn = "유턴" in text
    has_motorcycle = any(
        keyword in text
        for keyword in ("오토바이", "이륜차", "바이크", "모터사이클")
    )
    has_opposite_or_straight = any(
        keyword in text
        for keyword in ("맞은편", "반대편", "반대차선", "직진")
    )

    if has_uturn and has_motorcycle and has_opposite_or_straight:
        protected_uturn = any(
            keyword in text
            for keyword in ("유턴신호", "신호에따라유턴", "유턴신호에따라")
        )
        motorcycle_signal_violation = any(
            keyword in text
            for keyword in (
                "오토바이신호위반",
                "오토바이가신호위반",
                "이륜차신호위반",
                "이륜차가신호위반",
                "적색신호직진",
            )
        )

        if protected_uturn and motorcycle_signal_violation:
            return {
                "rule_key": "signal_uturn_vs_motorcycle",
                "confidence": 95,
                "reason": (
                    "사고 설명에서 자동차의 신호유턴과 맞은편 이륜차의 "
                    "신호위반 직진이 확인됐습니다."
                ),
                "needs_confirmation": False,
            }

        return {
            "rule_key": "uturn_vs_motorcycle",
            "confidence": 90,
            "reason": (
                "사고 설명에서 유턴 자동차와 맞은편 직진 이륜차의 충돌이 "
                "확인됐습니다. 신호 조건이 입력되지 않아 상시유턴 기준을 "
                "우선 적용합니다."
            ),
            "needs_confirmation": True,
        }

    return None


def get_rule_options():
    return {
        rule["name"]: rule_key
        for rule_key, rule in FAULT_RULES.items()
    }


def get_fault_rule(rule_key):
    return FAULT_RULES.get(rule_key)
