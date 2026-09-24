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
}


def get_rule_options():
    return {
        rule["name"]: rule_key
        for rule_key, rule in FAULT_RULES.items()
    }


def get_fault_rule(rule_key):
    return FAULT_RULES.get(rule_key)