import pytest
from accident_taxonomy import classify_description, SCENARIOS
from accident_classifier import recommend_accident_type


CASES = [
 ('rear_end','앞차를 추돌했습니다.'),
 ('stopped_rear_end','신호 대기 중 뒤에서 추돌했습니다.'),
 ('lane_change','옆 차량이 차로 변경 중 충돌했습니다.'),
 ('sudden_lane_change','정체 차로에서 갑자기 끼어들어 사고가 났습니다.'),
 ('simultaneous_lane_change','두 차량이 동시에 차로 변경하다 충돌했습니다.'),
 ('lane_reduction_merge','차로가 줄어드는 구간에서 합류하다 충돌했습니다.'),
 ('ramp_merge','램프에서 본선으로 합류하다 충돌했습니다.'),
 ('crossing_straight','직진차량이랑 좌측에서 직진하는 차량이랑 추돌'),
 ('left_turn_straight','교차로에서 좌회전 차량과 직진 차량이 충돌했습니다.'),
 ('right_turn_straight','우회전 차량과 직진 차량이 충돌했습니다.'),
 ('uturn','유턴 중 차량과 충돌했습니다.'),
 ('roundabout','회전교차로에서 진입하다 충돌했습니다.'),
 ('centerline','맞은편 차량이 중앙선을 넘어 충돌했습니다.'),
 ('reversing','주차장에서 후진 중 충돌했습니다.'),
 ('parked_vehicle','주차장에 주차된 차량과 충돌했습니다.'),
 ('starting','정차 후 출발하다 차량과 충돌했습니다.'),
 ('door_opening','주차장에서 문을 열다가 접촉 사고가 났습니다.'),
 ('pedestrian_crosswalk','횡단보도에서 보행자와 충돌했습니다.'),
 ('pedestrian','보행자와 충돌했습니다.'),
 ('bicycle','자전거와 충돌했습니다.'),
 ('motorcycle','오토바이와 충돌했습니다.'),
 ('single_vehicle','가드레일과 충돌했습니다.'),
 ('chain_collision','앞차를 추돌한 뒤 3중 추돌 사고가 났습니다.'),
 ('parking','주차장에서 차량과 충돌했습니다.'),
 ('narrow_road','좁은 도로에서 마주 오는 차량과 충돌했습니다.'),
]


@pytest.mark.parametrize('expected,text', CASES)
def test_type_conditions(expected,text):
    assert [x['key'] for x in classify_description(text)] == [expected]


@pytest.mark.parametrize('text', [
 '후진 사고가 아닙니다.', '중앙선 침범은 없었습니다.',
 '앞차를 추돌하지 않았습니다.', '좌회전 사고인지 모르겠습니다.',
 '좌회전 사고가 아니고 직진 사고입니다.', '차로 변경 사고 여부를 확인해 주세요.',
 '앞차를 추돌했나요?', '앞차 추돌을 가정한 시험입니다.',
 '주차장을 지나가고 자전거도 보입니다.',
])
def test_non_assertions_do_not_become_types(text):
    assert classify_description(text) == []


def test_conflicting_events_retained_without_selecting_ratio():
    result=recommend_accident_type({}, {}, {}, 1280,720,
        situation='좌회전 차량과 직진 차량이 충돌했습니다. 뒤에서 후방 추돌도 발생했습니다.')
    assert len(result['type_candidates'])==2
    assert result['rule_key'] is None
    assert result['requires_rule_review']


def test_crossing_description_has_no_false_visual_confirmation():
    result=recommend_accident_type({}, {}, {},1280,720,situation=CASES[7][1])
    assert result['type_candidates'][0]['key']=='crossing_straight'
    assert result['classification_source']=='user_description'
    assert result['visual_evidence']==[]
    assert result['rule_key'] is None


def test_single_crossing_track_does_not_require_two_external_cars():
    points=[(100+i*40,400) for i in range(12)]
    boxes=[[x-30-i*2,y-20-i,x+30+i*2,y+20+i] for i,(x,y) in enumerate(points)]
    result=recommend_accident_type({1:points},{1:boxes},{1:'car'},1280,720,
        ego_motion={'maneuver':'straight','consistency':.9})
    assert result['classification_source']=='visual_motion'
    assert result['rule_key'] is None


def test_catalog_coverage():
    assert {item['key'] for item in SCENARIOS}=={key for key,_ in CASES}
