MODIFIER_RULES = [
    {
        "key": "phone_use",
        "name": "운전 중 휴대전화 사용",
        "level": "현저한 과실",
        "fault_addition": 10,
        "keywords": (
            "휴대전화 사용",
            "핸드폰 사용",
            "휴대폰 사용",
            "스마트폰 사용",
            "전화하면서 운전",
            "문자하면서 운전",
        ),
        "reason": "운전 중 휴대전화 사용으로 전방주시 의무를 위반한 경우",
    },
    {
        "key": "distracted_driving",
        "name": "현저한 전방주시 의무 위반",
        "level": "현저한 과실",
        "fault_addition": 10,
        "keywords": (
            "한눈을 팔",
            "전방주시 태만",
            "전방주시 위반",
            "전방을 보지 않",
            "내비게이션 조작",
            "영상 시청",
        ),
        "reason": "한눈팔기 등으로 전방주시 의무 위반이 현저한 경우",
    },
    {
        "key": "speeding_10_to_20",
        "name": "제한속도 10km/h 이상 20km/h 미만 초과",
        "level": "현저한 과실",
        "fault_addition": 10,
        "keywords": (
            "10km/h 이상 과속",
            "10km 이상 과속",
            "제한속도보다 10km",
            "제한속도 10km 초과",
        ),
        "reason": "제한속도를 10km/h 이상 20km/h 미만 초과한 경우",
    },
    {
        "key": "speeding_20_or_more",
        "name": "제한속도 20km/h 이상 초과",
        "level": "중대한 과실",
        "fault_addition": 20,
        "keywords": (
            "20km/h 이상 과속",
            "20km 이상 과속",
            "제한속도보다 20km",
            "제한속도 20km 초과",
        ),
        "reason": "제한속도를 20km/h 이상 초과한 경우",
    },
    {
        "key": "drunk_driving",
        "name": "음주운전",
        "level": "중대한 과실",
        "fault_addition": 20,
        "keywords": ("음주운전", "술을 마시고 운전", "혈중알코올농도"),
        "reason": "혈중알코올농도 0.03% 이상의 음주운전인 경우",
    },
    {
        "key": "unlicensed_driving",
        "name": "무면허 운전",
        "level": "중대한 과실",
        "fault_addition": 20,
        "keywords": ("무면허 운전", "면허 없이 운전", "운전면허가 없"),
        "reason": "유효한 운전면허 없이 운전한 경우",
    },
    {
        "key": "drug_driving",
        "name": "약물운전",
        "level": "중대한 과실",
        "fault_addition": 20,
        "keywords": ("약물운전", "마약을 복용", "약물을 복용하고 운전"),
        "reason": "약물의 영향으로 정상적인 운전이 어려운 경우",
    },
    {
        "key": "reckless_driving",
        "name": "난폭운전",
        "level": "중대한 과실",
        "fault_addition": 20,
        "keywords": ("난폭운전", "보복운전", "위협 운전", "고의로 위협"),
        "reason": "난폭운전 또는 공동위험행위가 사고에 영향을 준 경우",
    },
]


def detect_fault_modifiers(situation):
    normalized_text = (situation or "").lower().replace(" ", "")
    detected = []
    for rule in MODIFIER_RULES:
        if any(
            keyword.lower().replace(" ", "") in normalized_text
            for keyword in rule["keywords"]
        ):
            detected.append(rule.copy())

    if any(item["key"] == "speeding_20_or_more" for item in detected):
        detected = [
            item for item in detected if item["key"] != "speeding_10_to_20"
        ]
    return detected
