"""Accident candidates, not legal findings. No fault percentages live here.

Text matches describe claims supplied by the user. Visual corroboration only
describes detector output; it never verifies signals, priority or a collision.
"""
import re


def spec(key, title, groups, checks, rule=None, supersedes=()):
    return dict(key=key, title=title, groups=groups, required_checks=checks,
                compatible_rule=rule, supersedes=supersedes)


# Each group must match within one non-negated clause. Alternatives use |.
SCENARIOS = [
    spec('rear_end', '동일 방향 후방 추돌', [r'앞차.{0,4}(추돌|충돌)|앞차후미|후방추돌|뒤에서.{0,4}(추돌|충돌)|뒤차.{0,4}(추돌|충돌)'],
         ['실제 충돌 상대', '두 차량의 동일 방향 진행', '급제동·끼어들기 여부'], 'rear_end'),
    spec('stopped_rear_end', '정차·신호대기 차량 후방 추돌', [r'정차|신호대기|정지중', r'후방|뒤에서|뒤차|앞차'],
         ['정차 이유와 위치', '충돌 부위', '직전 차로 변경 여부'], supersedes=('rear_end',)),
    spec('lane_change', '차로 변경 중 충돌', [r'차로변경|차선변경|진로변경|끼어들'],
         ['변경한 차량', '차선 통과 시점', '방향지시등과 회피 가능성'], 'lane_change'),
    spec('sudden_lane_change', '정체 차로에서 급진입', [r'정체', r'갑자기|급하게|급차로|급차선', r'끼어들|차로변경|차선변경'],
         ['정체 차로 여부', '갑작스러운 진입 여부', '직진 차량 위치'], 'sudden_lane_change', ('lane_change',)),
    spec('simultaneous_lane_change', '양쪽 차량 동시 차로 변경', [r'동시에|동시|서로|양쪽|두차량', r'차로변경|차선변경|진로변경'],
         ['두 차량의 출발 차로', '각 변경 시작 시점', '충돌 차로'], supersedes=('lane_change','sudden_lane_change')),
    spec('lane_reduction_merge', '차로 감소 구간 합류', [r'차로감소|차선감소|차로가줄|차선이줄|차로가없어|차선이없어', r'합류|진입'],
         ['차로 감소 표지', '본선·합류 차량 구분', '진입 순서'], 'merge'),
    spec('ramp_merge', '진입로·램프에서 본선 합류', [r'램프|진입로|고속도로입구|나들목|ic', r'합류|본선'],
         ['진입로 경계', '본선 차량 위치', '합류 시점']),
    spec('crossing_straight', '교차 방향 직진 차량 간 충돌', [r'직진', r'좌측에서|왼쪽에서|우측에서|오른쪽에서|교차로|교차방향|측면에서'],
         ['각 차량의 신호', '직진 여부', '도로 폭', '교차로 진입 순서']),
    spec('left_turn_straight', '좌회전 차량과 직진 차량 충돌', [r'좌회전', r'직진'],
         ['신호·비보호 여부', '각 차량의 진행 방향', '충돌 지점'], supersedes=('crossing_straight',)),
    spec('right_turn_straight', '우회전 차량과 직진 차량 충돌', [r'우회전', r'직진'],
         ['우회전 전 정지 여부', '각 차량의 신호', '진입 차로'], supersedes=('crossing_straight',)),
    spec('uturn', '유턴 중 충돌', [r'유턴|u턴'],
         ['유턴 허용 조건', '상대 진행 방향', '각 차량의 신호']),
    spec('roundabout', '회전교차로 진입·회전 중 충돌', [r'회전교차로|로터리|로타리'],
         ['진입 차량과 회전 차량 구분', '진입 시점', '차로 변경 여부']),
    spec('centerline', '중앙선 침범·역주행 관련 충돌', [r'중앙선침범|중앙선을넘|중앙선을침범|역주행'],
         ['중앙선 위치', '침범 차량', '일방통행 여부']),
    spec('reversing', '후진 중 충돌', [r'후진|뒤로가|뒤로움직'],
         ['후진 차량', '상대 차량 정지 여부', '후방 시야'], supersedes=('parking',)),
    spec('parked_vehicle', '주차 차량과 충돌', [r'주차된|주차해둔|주차중인|주차한차|주차차량'],
         ['주차 위치', '통행 방해 여부', '충돌 차량 움직임'], supersedes=('parking',)),
    spec('starting', '정차 후 출발·도로 진입 중 충돌', [r'정차후출발|출발하다|출발하던|출발하는|도로로진입|골목에서나|골목에서진입'],
         ['출발 위치', '도로 진입 경계', '진행 차량과의 거리']),
    spec('door_opening', '차량 문 열림 사고', [r'문을열|문열|개문'],
         ['문을 연 시점', '통과 차량 위치', '정차 위치'], supersedes=('parked_vehicle','parking')),
    spec('pedestrian_crosswalk', '횡단보도 보행자 사고', [r'횡단보도', r'보행자|사람|행인'],
         ['보행 신호', '횡단 시작 시점', '차량 진행 방향'], supersedes=('pedestrian',)),
    spec('pedestrian', '보행자와 차량 충돌', [r'보행자|행인|사람을|사람과'],
         ['보행 위치', '횡단 여부', '시야 가림 여부']),
    spec('bicycle', '자전거 관련 충돌', [r'자전거'],
         ['자전거 진행 방향', '주행 공간', '각 신호']),
    spec('motorcycle', '이륜차 관련 충돌', [r'오토바이|이륜차|모터사이클'],
         ['이륜차 진행 방향', '차로 변경 여부', '각 신호']),
    spec('single_vehicle', '시설물 충돌·도로 이탈 단독사고', [r'가드레일|전봇대|벽에|벽과|도로이탈|도로를벗|단독사고'],
         ['다른 차량 개입 여부', '시설물 위치', '노면 상태']),
    spec('chain_collision', '연쇄·다중 추돌', [r'연쇄추돌|연쇄충돌|다중추돌|다중충돌|[3-9]중추돌|삼중추돌'],
         ['최초 충돌 순서', '각 차량 정지 여부', '후속 충돌 관계'], supersedes=('rear_end','stopped_rear_end')),
    spec('parking', '주차장 내 차량 충돌', [r'주차장'],
         ['통로 우선관계', '진행·후진 차량 구분', '시야 확보']),
    spec('narrow_road', '좁은 도로의 대향 차량 충돌', [r'좁은도로|좁은길|골목길', r'마주|맞은편|반대편'],
         ['통행 공간', '정지·양보 여부', '각 차량 위치']),
]

COLLISION = re.compile(r'충돌|추돌|부딪|부딧|접촉|사고|쳤|치었')
NEGATION = re.compile(r'아니|아닌|아닙|않|없|못|불명|모르|가정|예시|시험|테스트|여부|했는지|했나요|인가요|\?')


def classify_description(situation):
    matches = {}
    # Split contrast clauses too, so a denied manoeuvre does not become fact.
    clauses = re.split(r'[.!;\n]|하지만|그러나', situation or '')
    for clause in clauses:
        text = re.sub(r'\s+', '', clause).lower()
        if not COLLISION.search(text) or NEGATION.search(text):
            continue
        for item in SCENARIOS:
            hits = [re.search(pattern, text) for pattern in item['groups']]
            if all(hits):
                matches[item['key']] = {k: v for k, v in item.items() if k not in ('groups','supersedes')}
                matches[item['key']]['matched_terms'] = [hit.group(0) for hit in hits]
    suppressed = {key for item in SCENARIOS if item['key'] in matches for key in item['supersedes']}
    return [item for key, item in matches.items() if key not in suppressed]


def describe_candidates(matches):
    return ' / '.join(item['title'] for item in matches)


def attach_scenarios(result, situation, tracks, boxes, classes, width, height, ego, lane):
    """Expose text and visual evidence separately, and gate unsupported rules."""
    matches = classify_description(situation)
    visual = result.get('visual_candidate', result)
    evidence = []
    if visual.get('rule_key'):
        evidence.append('영상 이동 조건 후보: ' + visual.get('title', visual['rule_key']))
    for class_name, label in [('person','사람'),('bicycle','자전거'),('motorcycle','이륜차')]:
        if class_name in classes.values():
            evidence.append(label + ' 객체가 탐지됨 (충돌 당사자 여부 미확인)')
    if lane.get('lane_change_detected'):
        evidence.append('차선 기준 상대 위치 변화 탐지 (진로 변경 확정 아님)')
    if not matches:
        # A camera car is not a YOLO track: allow a single lateral vehicle as
        # a crossing candidate, never as a legal-rule match.
        from accident_classifier import get_track_features, VEHICLE_CLASSES
        for key, points in tracks.items():
            if classes.get(key) not in VEHICLE_CLASSES:
                continue
            f = get_track_features(list(points), list(boxes.get(key, [])), width, height)
            if (f and f['tracked_frames'] >= 6 and f['lateral_movement'] >= .12
                and abs(f['move_x']) > abs(f['move_y']) * 1.5
                and (f['start_x_ratio'] < .25 or f['start_x_ratio'] > .75)
                and abs(f['end_x_ratio']-.5) < abs(f['start_x_ratio']-.5)
                and f['area_growth'] > .15
                and ego.get('maneuver') == 'straight'
                and ego.get('consistency', 0) >= .62):
                return {**result, 'rule_key': None, 'confidence': 0, 'decision_status':'hold',
                    'title':'측면 진입·교차 진행 후보', 'type_candidates':[],
                    'classification_source':'visual_motion', 'requires_rule_review':True,
                    'visual_evidence':[f'차량 #{key}: 화면 측면에서 중앙 방향 이동 및 크기 증가'],
                    'required_checks':['실제 충돌 상대','차로 변경인지 교차로 진입인지','진행 방향과 신호'],
                    'reason':'한 차량의 측면 접근이 탐지됐습니다. 차로 변경과 교차로 진입을 구별하고 충돌 상대를 확인하기 전에는 과실비율을 계산하지 않습니다.'}
        if result.get('premise_source') == 'user_description_unverified':
            return {**result, 'rule_key':None, 'confidence':0, 'decision_status':'hold',
                'requires_rule_review':True, 'reason':'후방 추돌을 뒷받침하는 명확한 사고 설명이 확인되지 않았습니다. 부정·질문·가정 표현을 사실로 적용하지 않습니다.'}
        return result
    checks = list(dict.fromkeys(check for item in matches for check in item['required_checks']))
    result = {**result, 'type_candidates':matches, 'classification_source':'user_description',
              'visual_evidence':evidence, 'required_checks':checks}
    # Multiple applicable descriptions are retained instead of picking a
    # percentage by arbitrary priority. Even one text match is not visual proof.
    compatible = len(matches)==1 and matches[0]['compatible_rule'] == result.get('rule_key') and result.get('rule_key') is not None
    if not compatible:
        result.update(rule_key=None, confidence=0, decision_status='hold', requires_rule_review=True,
            title=describe_candidates(matches) + ' — 설명 기반 후보',
            reason='입력 설명에서 해당 사고 유형의 조건을 찾았습니다. 사용자가 제공한 정보이며 영상으로 확정한 사실은 아닙니다. '
                   '유형 후보는 표시하되, 적용 기준의 전제와 충돌 당사자가 확인되지 않아 과실비율은 보류합니다.')
    else:
        result['reason'] += ' 사고 유형 조건은 입력 설명에서 추출했으며 신호·우선관계는 영상으로 검증되지 않았습니다.'
    return result
