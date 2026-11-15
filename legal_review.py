"""Conditional guidance; never turn unverified video facts into a verdict."""
def build_legal_review(recommendation, include_options=True):
    keys = {x['key'] for x in recommendation.get('type_candidates', [])}
    crossing = 'crossing_straight' in keys
    law26 = 'https://law.go.kr/lsLinkCommonInfo.do?chrClsCd=010202&lsJoLnkSeq=1031179903'
    source = 'https://accident.knia.or.kr/myaccident-content?chartNo=%EC%B0%A812-1&chartType=1'
    review = {
        'title': '과실 판단에 적용할 법적 기준',
        'summary': '영상에서 확인한 이동과 입력 설명을 구분하여 검토합니다. 신호, 진행 방향, 회피 가능성 등 확인되지 않은 사실을 위반으로 단정하지 않습니다.',
        'laws': [{'title': '도로교통법 제48조 제1항 · 안전운전 의무',
                  'text': '당시 교통 상황에서 위험을 인지하고 안전하게 조향·제동할 수 있었는지 검토합니다. 이 조항만으로 특정 과실비율이 정해지지는 않습니다.',
                  'url': 'https://www.law.go.kr/lsLinkCommonInfo.do?chrClsCd=010202&lsJoLnkSeq=1030974833'}],
        'conditional_ratios': [],
        'notice': '아래 비율은 명시된 조건에서의 기본 기준이며 이 영상의 확정 과실비율이 아닙니다. 신호·표지·도로 폭·진입 순서 및 수정요소에 따라 달라집니다.'}
    if 'alley_entry' in keys:
        review['title'] = '골목길 측면 진입 사고 검토'
        review['summary'] = '골목길 진입이라는 사용자 설명을 전제로 검토합니다. 일반 교차로 직진의 기본 비율을 그대로 적용하지 않습니다. 골목 교차로인지 건물·주차장 출입구인지, 양측 시야와 정지·서행 여부를 구분해야 합니다. 갑자기 나타났다는 사실만으로 상대 차량의 일방 과실을 확정하지 않습니다.'
        review['laws'].insert(0, {
            'title': '도로교통법 제31조 제1·2항 · 서행과 일시정지',
            'text': '교통정리가 없는 교차로에서는 서행해야 합니다. 그중 좌우를 확인할 수 없거나 교통이 빈번한 교차로에서는 일시정지가 요구됩니다. 해당 조건과 양측 운전 행동은 따로 확인해야 합니다.',
            'url': 'https://www.law.go.kr/LSW/lsLinkCommonInfo.do?chrClsCd=010202&lsJoLnkSeq=1030974729'})
        review['notice'] = '골목길이라는 설명과 영상 이동 단서는 구분됩니다. 도로 형태와 시야·정지 여부가 확인되기 전에는 특정 기본 비율을 이 사고의 비율로 표시하지 않습니다.'
        return review
    if crossing:
        review['summary'] = '교차 방향 직진 충돌이라는 입력 설명을 전제로 검토합니다. 상대가 왼쪽에서 왔다는 사실만으로 상대방의 신호위반이나 전적인 책임을 단정할 수 없습니다. 신호가 없었다면 진입 순서, 도로 폭, 동시 진입 여부가 핵심입니다.'
        review['laws'] = [
            {'title':'도로교통법 제26조 제1항 · 먼저 진입한 차량', 'text':'교통정리가 없는 교차로에서는 이미 진입한 차량에 양보해야 합니다. 어느 차량이 명확히 먼저 진입했는지 확인해야 합니다.', 'url':law26},
            {'title':'도로교통법 제26조 제2항 · 도로 폭', 'text':'신호로 교통정리가 되지 않는 경우, 더 넓은 도로에서 진입하는 차량에 양보해야 합니다. 도로 폭이 다르면 아래 동일 폭 기준을 그대로 적용하지 않습니다.', 'url':law26},
            {'title':'도로교통법 제26조 제3항 · 동시 진입', 'text':'교통정리가 없는 교차로에 동시에 진입하려는 경우에는 우측 도로 차량에 양보해야 합니다. 블랙박스 차량이 상대 차량 기준 우측 차량인지 구분해야 합니다.', 'url':law26},
            {'title':'도로교통법 제5조 · 신호 준수', 'text':'신호로 통제되는 교차로라면 각 차량의 진입 신호를 먼저 확인해야 합니다. 이 경우 신호 없는 교차로 기준을 적용하지 않습니다.', 'url':'https://www.law.go.kr/LSW/lsLinkCommonInfo.do?chrClsCd=010202&lsJoLnkSeq=1030973033'},
        ] + review['laws']
        common = '신호로 통제되지 않는 동일 폭 교차로에서 양쪽 모두 직진하고, 별도 일시정지·일방통행 표지가 없는 경우'
        review['conditional_ratios'] = [
            {'condition':common+' · 동시 진입', 'a':'우측 도로 차량', 'b':'좌측 도로 차량', 'ratio':'40 : 60', 'reason':'동시 진입 시 우측 차량의 우선관계를 반영한 기본 기준입니다.', 'url':source},
            {'condition':common+' · 명확한 선진입 확인', 'a':'먼저 진입한 차량', 'b':'나중에 진입한 차량', 'ratio':'30 : 70', 'reason':'명확한 선진입이 확인된 경우의 기준입니다. 차량의 화면 등장 순서만으로 선진입을 인정하지 않습니다.', 'url':source},
        ]
    if include_options and recommendation.get('temporal_candidates'):
        crossing_review = build_legal_review({'type_candidates': [{'key': 'crossing_straight'}]}, False)
        crossing_review['summary'] = crossing_review['summary'].replace('입력 설명', '사용자가 선택한 사고 유형')
        alley_review = build_legal_review({'type_candidates': [{'key': 'alley_entry'}]}, False)
        alley_review['summary'] = alley_review['summary'].replace('사용자 설명', '사용자가 선택한 사고 유형')
        review['review_options'] = [
            {'key': 'alley_entry', 'title': '골목길에서 차량이 갑자기 측면 진입', 'review': alley_review},
            {'key': 'crossing_straight', 'title': '교차 방향에서 두 차량이 직진하다 충돌', 'review': crossing_review}]
        if recommendation.get('approach_assessment', {}).get('short_lateral_approach'):
            review['conditional_ratios'] = []
            review['summary'] = '짧은 시간의 측면 접근을 찾았습니다. 골목길 진입인지 일반 교차로 직진인지 먼저 확인해주세요. 영상의 탐지 시간은 실제 반응 시간이나 충돌까지의 시간이 아닙니다.'
    return review
