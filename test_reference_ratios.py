from legal_review import build_legal_review

def review(side=None, key='alley_entry'):
 return build_legal_review({'type_candidates':[{'key':key}], 'temporal_candidates':[{'side':side}] if side else []})

def test_left_right_mapping_and_unknown():
 assert review('왼쪽')['provisional_estimate']['camera_percent']==40
 assert review('오른쪽')['provisional_estimate']['camera_percent']==60
 assert review()['provisional_estimate']['camera_percent'] is None

def test_no_arbitrary_percent_without_a_supported_scenario():
 assert build_legal_review({})['conditional_ratios']==[]
 assert review('왼쪽','parking')['conditional_ratios']==[]
 assert build_legal_review({'type_candidates':[{'key':'alley_entry'},{'key':'left_turn_straight'}]})['conditional_ratios']==[]

def test_reference_sources_and_sum():
 r=review('왼쪽')
 assert len(r['conditional_ratios'])==4
 assert [x['ratio'] for x in r['conditional_ratios']]==['40 : 60','30 : 70','30 : 70','20 : 80']
 for row in r['conditional_ratios']:
  assert sum(map(int,row['ratio'].split(':')))==100
  assert row['url'].startswith('https://accident.knia.or.kr/')
 assert r['provisional_estimate']['assumptions']
 assert len([law for law in r['laws'] if '제31조' in law['title']])==1

def test_rapid_approach_never_adds_fault_points():
 rec={'type_candidates':[{'key':'alley_entry'}], 'temporal_candidates':[{'side':'왼쪽'}], 'approach_assessment':{'short_lateral_approach':True,'observed_seconds':.5}}
 assert build_legal_review(rec)['provisional_estimate']['camera_percent']==40
