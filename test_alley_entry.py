from accident_classifier import apply_temporal_evidence
from accident_taxonomy import classify_description
from legal_review import build_legal_review

def history(count=16, sparse=False):
 rows=[]
 for i in range(count):
  t=i/(count-1);cx=80+470*t;w=80+400*t;h=50+250*t
  rows.append([] if sparse and i%4 else [{'track_id':1,'class_name':'car','box':[cx-w/2,500-h/2,cx+w/2,500+h/2]}])
 return rows

def test_short_observation_is_not_collision_or_road_context():
 r=apply_temporal_evidence({},history(),1280,720,30)
 assert r['approach_assessment']['short_lateral_approach']
 assert r['approach_assessment']['road_context']=='unconfirmed'
 assert not r['temporal_candidates'][0]['contact_confirmed']
 assert not build_legal_review(r)['conditional_ratios']

def test_slower_motion_not_short():
 r=apply_temporal_evidence({},history(90),1280,720,30)
 assert not r['approach_assessment']['short_lateral_approach']

def test_sparse_tracking_not_short():
 r=apply_temporal_evidence({},history(28,True),1280,720,30)
 assert not r['approach_assessment']['short_lateral_approach']

def test_alley_overrides_generic_crossing():
 types=classify_description('골목길에서 직진 중 왼쪽에서 차량이 갑자기 진입해 충돌')
 assert [x['key'] for x in types]==['alley_entry']
 review=build_legal_review({'type_candidates':types})
 assert review['conditional_ratios'][0]['ratio']=='40 : 60'
 assert review['provisional_estimate']['kind']=='assumption_based_reference'
 assert review['provisional_estimate']['camera_percent'] is None
 assert '제31조' in review['laws'][0]['title']

def test_negative_and_ordinary_alley_not_sudden_accident():
 assert classify_description('골목길에서 갑자기 진입한 사고가 아닙니다')==[]
 assert classify_description('골목길 직진 중 사고')==[]
