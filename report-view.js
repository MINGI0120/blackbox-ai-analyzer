/* Legal-duty summaries verified against 국가법령정보센터 on 2026-10-25.
   Duties explain the review framework; they do not prescribe these percentages. */
(function(root){
 const laws={
  distance:{title:'도로교통법 제19조 제1항 · 안전거리',text:'앞차가 급히 멈추더라도 충돌을 피할 수 있는 간격을 두고 주행해야 합니다.',url:'https://www.law.go.kr/lsLinkCommonInfo.do?chrClsCd=010202&lsJoLnkSeq=1030974799'},
  change:{title:'도로교통법 제19조 제3항 · 진로 변경',text:'진로를 바꾸려는 쪽에서 오는 차량의 정상적인 주행을 방해할 위험이 있으면 진로를 변경해서는 안 됩니다.',url:'https://www.law.go.kr/lsLinkCommonInfo.do?chrClsCd=010202&lsJoLnkSeq=1030974917'},
  uturn:{title:'도로교통법 제18조 제1항 · 유턴',text:'다른 차량이나 보행자의 정상적인 통행을 방해할 위험이 있는 상황에서는 유턴을 해서는 안 됩니다.',url:'https://www.law.go.kr/lsLinkCommonInfo.do?chrClsCd=010202&lsJoLnkSeq=1030973159'},
  signal:{title:'도로교통법 제5조 제1항 · 신호 준수',text:'운전자는 교통안전시설의 신호와 지시, 교통정리를 하는 경찰공무원 등의 신호와 지시를 따라야 합니다.',url:'https://www.law.go.kr/LSW/lsLinkCommonInfo.do?chrClsCd=010202&lsJoLnkSeq=1030973033'},
  intersection:{title:'도로교통법 제26조 제2·4항 · 교차로 양보',text:'신호로 교통정리가 되지 않는 교차로에서는 더 넓은 도로에서 진입하는 차량에 양보해야 하며, 좌회전 차량은 직진·우회전 차량에 양보해야 합니다.',url:'https://www.law.go.kr/LSW/lsLinkCommonInfo.do?lsJoLnkSeq=1007526125'},
  safe:{title:'도로교통법 제48조 제1항 · 안전운전',text:'도로 상황에 맞게 조향·제동 장치를 다루고, 다른 사람에게 위험을 주는 속도나 방법으로 운전하지 않아야 합니다.',url:'https://www.law.go.kr/lsLinkCommonInfo.do?lsJoLnkSeq=1030974833'}
 };
 const types={
  rear_end:{laws:['distance','safe'],reason:'뒤에서 진행한 차량이 앞차와 충분한 간격을 유지하고 정지에 대비했는지가 핵심입니다. 다만 앞차의 불가피하지 않은 급제동이나 끼어들기 등 별도 사정이 확인되면 양측 책임을 다시 살펴봐야 합니다.',check:'앞차의 정지 이유, 차간 거리, 충돌 직전 끼어들기 여부'},
  lane_change:{laws:['change','safe'],reason:'차로를 바꾼 차량이 이미 진행 중인 차량의 진로를 방해했는지를 우선 살펴봅니다. 직진 차량도 상대의 진입을 인지한 시점과 사고를 피할 여지가 있었는지 함께 확인해야 합니다.',check:'진로 변경 시작 시점, 방향지시등, 두 차량의 위치와 속도'},
  sudden_lane_change:{laws:['change','safe'],reason:'정체 구간에서 갑자기 진입한 차량이 옆 차로의 정상적인 통행을 방해했는지가 중요합니다. 옆 차로 차량에게 충돌을 예상하거나 피할 시간이 있었는지도 책임 판단에 영향을 줍니다.',check:'정체 여부, 진입의 갑작스러움, 직진 차량의 회피 가능성'},
  merge:{laws:['change','safe'],reason:'차로가 줄어드는 구간에서 합류 차량이 본선 차량의 진행을 방해했는지 살펴봅니다. 본선 차량의 진행 속도와 합류를 인지할 수 있었던 거리도 함께 확인해야 합니다.',check:'차로 감소 표지, 합류 시작 위치, 양쪽 차량의 주행 속도'},
  intersection:{laws:['intersection','safe'],reason:'신호가 없는 교차로의 대로 직진차와 소로 좌회전차 사고라는 전제에서, 소로 진입·좌회전 차량의 양보 의무가 중요한 판단 요소입니다. 먼저 진입한 차량과 실제 도로 폭을 확인해야 합니다.',check:'신호 유무, 교차 도로의 폭, 진입 순서와 각 차량의 진행 방향'},
  narrow_road:{laws:['safe'],reason:'좁은 도로에서는 양쪽 차량 모두 상대의 진행을 살피고 안전한 속도와 간격을 유지했는지가 중요합니다. 어느 쪽이 진로를 침범했는지, 양보할 공간이 있었는지를 확인해야 합니다.',check:'충돌 위치, 도로 폭, 진로 침범과 정차·양보 가능성'},
  uturn_vs_motorcycle:{laws:['uturn','safe'],reason:'상시유턴 중 맞은편 직진 이륜차와 충돌한 사고라는 전제에서는, 유턴 차량이 직진 차량의 통행을 방해했는지를 중점적으로 살펴봅니다. 유턴 가능 조건과 이륜차의 실제 속도·신호도 확인해야 합니다.',check:'유턴 허용 조건, 맞은편 차량의 신호와 속도, 충돌 전 위치'},
  signal_uturn_vs_motorcycle:{laws:['signal','uturn'],reason:'유턴 차량이 허용 신호에 따랐고 맞은편 이륜차가 신호를 위반했다는 전제라면, 이륜차의 신호 준수 의무가 중요한 판단 요소입니다. 입력된 설명만으로 신호위반을 확정하지 않으며 실제 신호와 진입 시점을 확인해야 합니다.',check:'유턴 신호·표지, 이륜차의 진입 신호, 각 차량의 교차로 진입 시점'}
 };
 function explain(report,key){
  if(!report.fault)return {held:true,title:'지금은 과실비율을 정하기 어렵습니다.',reason:report.recommendation?.reason||'사고 유형을 뒷받침하는 증거가 충분하지 않습니다. 영상의 신호·진행 방향·충돌 전후 장면을 확인해 주세요.',laws:[]};
  const type=types[key]||{laws:['safe'],reason:'양쪽 차량이 당시 도로 상황에 맞게 운전했는지, 위험을 인지하고 피할 수 있었는지를 확인해야 합니다.',check:'진행 방향, 신호, 속도와 충돌 전후 장면'};
  const f=report.fault;
  const subject=f.fault_a>f.fault_b?report.rule.vehicle_a:f.fault_b>f.fault_a?report.rule.vehicle_b:null;
  return {held:false,title:subject?`${subject}의 책임을 더 크게 보는 예상입니다.`:'두 차량의 책임을 비슷하게 보는 예상입니다.',reason:type.reason,check:type.check,laws:type.laws.map(k=>laws[k]),basis:report.rule_source==='manual'?'직접 선택한 사고 유형을 전제로 검토했습니다.':report.rule_source==='situation'?'입력한 사고 설명을 우선 반영한 유형으로 검토했습니다.':'영상에서 추천한 사고 유형을 전제로 검토했습니다.'};
 }
 function render(container,report,key){
  container.replaceChildren();const doc=container.ownerDocument;
  function add(parent,tag,content,cls){const el=doc.createElement(tag);if(content!=null)el.textContent=content;if(cls)el.className=cls;parent.append(el);return el;}
  const info=explain(report,key);
  const rec=report.recommendation||{};
  function scenarioDetails(){
   if(rec.type_candidates?.length){add(container,'h3','사고 유형 후보 · 입력 설명 기반');for(const item of rec.type_candidates){const row=add(container,'article',null,'verdict-check');add(row,'b',item.title);add(row,'p','설명에서 찾은 표현: '+(item.matched_terms||[]).join(', '));}}
   if(rec.visual_evidence?.length){add(container,'h3','영상에서 얻은 단서');for(const value of rec.visual_evidence)add(container,'p',value);}
   if(rec.required_checks?.length){add(container,'h3','비율 판단 전에 확인할 내용');const ul=add(container,'ul');for(const value of rec.required_checks)add(ul,'li',value);}
  }

  function legalReview(){
   const review=report.legal_review;
   add(container,'h3','판단이 어려운 부분은 법적 기준으로 설명합니다');
   if(review){
    add(container,'p',review.summary);
    if(review.conditional_ratios?.length){
     add(container,'h3','조건별 참고 과실비율 · 현재 영상의 판정값 아님');
     add(container,'p',review.notice,'legal-note');
     for(const item of review.conditional_ratios){const row=add(container,'article',null,'verdict-check');add(row,'b',item.condition);add(row,'h3',item.ratio);add(row,'p',item.a+' : '+item.b);add(row,'p',item.reason);const link=add(row,'a','손해보험협회 차12-1 기준 확인 ↗');link.href=item.url;link.target='_blank';link.rel='noopener';}
    }
    const legal=add(container,'div',null,'legal-basis');for(const law of review.laws){const row=add(legal,'article');const link=add(row,'a',law.title+' ↗');link.href=law.url;link.target='_blank';link.rel='noopener';add(row,'p',law.text);}
   }else{add(container,'p','이전 분석 결과에는 법적 설명이 저장되지 않았습니다. 다시 분석하면 상황별 설명이 함께 표시됩니다.');}
   const keys=(rec.type_candidates||[]).map(x=>x.compatible_rule||x.key);
   for(const k of [...new Set(keys)]){const type=types[k];if(type){add(container,'p',type.reason);for(const name of type.laws){const law=laws[name];const row=add(container,'article',null,'verdict-check');const link=add(row,'a',law.title+' ↗');link.href=law.url;link.target='_blank';link.rel='noopener';add(row,'p',law.text);}}}
  }
  const choices=report.legal_review?.review_options||[];
  if(info.held && choices.length){
   const confirmation=add(container,'div',null,'verdict-check scenario-confirmation');
   add(confirmation,'b','영상에서 찾은 측면 접근이 어떤 사고였나요?');
   add(confirmation,'p','설명을 다시 입력할 필요 없이 유형을 선택해 참고 기준을 확인하세요. 선택한 유형은 영상으로 확정된 사실과 구분합니다.');
   const label=add(confirmation,'label',null,'vehicle-mapping');add(label,'span','사고 유형 확인');
   const selector=add(label,'select');selector.setAttribute('aria-label','사고 유형 확인');
   const empty=add(selector,'option','선택해 주세요 / 아직 모르겠습니다');empty.value='';
   for(const option of choices){const el=add(selector,'option',option.title);el.value=option.key;}
   const other=add(selector,'option','회전·차로 변경 등 다른 사고');other.value='other';
   selector.value=report.legal_review.selected_key||'';
   selector.onchange=()=>{
    const choice=choices.find(x=>x.key===selector.value);
    const original=report._unselectedReview||report.legal_review;
    const review={...(choice?choice.review:original),review_options:choices,selected_key:selector.value};
    render(container,{...report,_unselectedReview:original,legal_review:review},key);
   };
   if(selector.value==='other')add(confirmation,'p','교차 방향 직진 기준은 적용하지 않습니다. 아래 영상 단서와 법적 설명을 확인해주세요.');
  }
  const references=(report.legal_review?.conditional_ratios||[]).filter(x=>/^\d+\s*:\s*\d+$/.test(x.ratio));
  if(info.held && references.length){
   container.className='result-block conditional-result';
   const tabs=add(container,'div',null,'reference-tabs');tabs.setAttribute('role','group');tabs.setAttribute('aria-label','참고 기준 비교');
   add(tabs,'span','적용 조건별 기준 보기');
   const panel=add(container,'div',null,'fault-focus conditional-panel');
   const buttons=[], vehicleChoices=new Map();
   function showReference(index){
    panel.replaceChildren();buttons.forEach((b,i)=>b.setAttribute('aria-pressed',String(i===index)));
    const item=references[index], values=item.ratio.split(':').map(Number);
    const hero=add(panel,'div',null,'verdict-hero');
    add(hero,'div','조건부 참고 과실비율 · 영상의 확정 판정 아님','verdict-kicker');
    add(hero,'h3',choices.find(x=>x.key===report.legal_review.selected_key)?.title||rec.type_candidates?.[0]?.title||'사고 유형별 기본 기준','verdict-type');
    add(hero,'p',item.condition,'reference-condition');
    const mapping=add(hero,'label',null,'vehicle-mapping');
    const isSide=item.a==='우측 도로 차량'&&item.b==='좌측 도로 차량';
    add(mapping,'span',isSide?'상대 차량은 어느 쪽 도로에서 왔나요?':'블랙박스 차량은 어느 역할인가요?');
    const select=add(mapping,'select');select.setAttribute('aria-label',isSide?'상대 차량 진입 방향':'블랙박스 차량 역할');
    [['','선택해 주세요'],['a',isSide?'상대 차량이 왼쪽에서 진입':item.a],['b',isSide?'상대 차량이 오른쪽에서 진입':item.b]].forEach(([v,t])=>{const o=add(select,'option',t);o.value=v;});
    select.value=vehicleChoices.get(index)||'';select.onchange=()=>{vehicleChoices.set(index,select.value);showReference(index);};
    const mapped=!!select.value, reverse=select.value==='b';
    const displayValues=mapped?(reverse?[values[1],values[0]]:values):[null,null];
    const roles=mapped?(reverse?[item.b,item.a]:[item.a,item.b]):['역할 선택 필요','역할 선택 필요'];
    const ratios=add(hero,'div',null,'verdict-ratios');
    for(let i=0;i<2;i++){const col=add(ratios,'article',null,'verdict-party party-'+(i?'b':'a'));add(col,'span',roles[i],'party-label');add(col,'h4',i?'상대 차량':'블랙박스 차량');const value=add(col,'div',null,'party-value');add(value,'strong',mapped?String(displayValues[i]):'—');if(mapped)add(value,'span','%');}
    const bar=add(hero,'div',null,'ratio-visual');bar.setAttribute('aria-hidden','true');for(let i=0;i<2;i++){const part=add(bar,'span',null,i?'ratio-b':'ratio-a');part.style.width=(mapped?displayValues[i]:50)+'%';if(!mapped)part.style.opacity='.2';}
    add(hero,'p','위 조건이 충족될 때의 기본 비율입니다.','verdict-headline');
    add(hero,'p',mapped?'선택하신 차량 역할을 기준으로 연결한 참고 비율이며 영상으로 확인된 역할은 아닙니다.':`차량 역할을 선택하면 비율이 연결됩니다. 원래 기준: ${item.a} ${values[0]}% / ${item.b} ${values[1]}%.`,'analysis-caption');
    const reasons=add(panel,'div',null,'verdict-reasons');add(reasons,'div','WHY THIS REFERENCE','eyebrow muted');add(reasons,'h3','이 기준을 참고하는 이유');add(reasons,'p',item.reason,'plain-reason');add(reasons,'p',report.legal_review.summary,'basis-line');
    if(report.situation){const quote=add(reasons,'div',null,'situation-quote');add(quote,'span','입력하신 사고 상황');add(quote,'p',report.situation);}
    const link=add(reasons,'a','손해보험협회 기준 원문 ↗','reference-source');link.href=item.url;link.target='_blank';link.rel='noopener';
    const legal=add(reasons,'div',null,'legal-basis');const legalItems=report.legal_review.laws||[];const selected=index===0?2:0;const other=add(reasons,'details',null,'reference-more-laws');add(other,'summary','관련 법 조항 더 보기');for(const [lawIndex,law] of legalItems.entries()){const row=add(lawIndex===selected||lawIndex===legalItems.length-1?legal:other,'article');const a=add(row,'a',law.title+' ↗');a.href=law.url;a.target='_blank';a.rel='noopener';add(row,'p',law.text);}
   }
   references.forEach((item,i)=>{const button=add(tabs,'button',item.condition.split(' · ').pop(),'reference-tab');button.type='button';button.onclick=()=>showReference(i);buttons.push(button);});
   showReference(0);
   const more=add(container,'div',null,'verdict-check');add(more,'b','실제 과실비율을 정하려면 추가 확인이 필요합니다');add(more,'p',info.reason);add(more,'p',report.legal_review.notice.replace('아래 비율','표시된 비율'));
   if(rec.required_checks?.length){const ul=add(more,'ul');for(const check of rec.required_checks)add(ul,'li',check);}
   if(rec.visual_evidence?.length){add(more,'b','영상에서 얻은 단서');for(const value of rec.visual_evidence)add(more,'p',value);}
   return;
  }
  if(info.held){container.className='result-block fault-focus held';add(container,'div','사고 분석 및 법적 검토','verdict-kicker');add(container,'h3',rec.temporal_candidates?.length?'영상에서 측면 접근 차량을 찾았습니다.':rec.type_candidates?.length?'사고 유형 후보를 찾았습니다. 과실비율은 추가 확인이 필요합니다.':info.title);add(container,'p',info.reason);legalReview();scenarioDetails();return;}
  container.className='result-block fault-focus';
  const hero=add(container,'div',null,'verdict-hero');add(hero,'div','예상 과실비율','verdict-kicker');add(hero,'h3',report.rule.name,'verdict-type');
  const ratios=add(hero,'div',null,'verdict-ratios');
  for(const side of ['a','b']){const col=add(ratios,'article',null,`verdict-party party-${side}`);add(col,'span','차량 '+side.toUpperCase(),'party-label');add(col,'h4',report.rule['vehicle_'+side]);const value=add(col,'div',null,'party-value');add(value,'strong',String(report.fault['fault_'+side]));add(value,'span','%');add(col,'p',`예상 범위 ${report.fault['range_low_'+side]}–${report.fault['range_high_'+side]}%`);}
  const ratioBar=add(hero,'div',null,'ratio-visual');const a=add(ratioBar,'span',null,'ratio-a');a.style.width=report.fault.fault_a+'%';const b=add(ratioBar,'span',null,'ratio-b');b.style.width=report.fault.fault_b+'%';ratioBar.setAttribute('aria-hidden','true');
  add(hero,'p',info.title,'verdict-headline');add(hero,'p','차량 A·B는 위에 표시된 역할입니다. 내 차·상대 차와 자동으로 대응하지 않습니다.','analysis-caption');
  const reasons=add(container,'div',null,'verdict-reasons');add(reasons,'div','WHY THIS ASSESSMENT','eyebrow muted');add(reasons,'h3','이렇게 판단한 이유');add(reasons,'p',info.basis,'basis-line');add(reasons,'p',info.reason,'plain-reason');
  if(report.situation){const quote=add(reasons,'div',null,'situation-quote');add(quote,'span','입력하신 사고 상황');add(quote,'p',report.situation.length>220?report.situation.slice(0,220)+'…':report.situation);}
  const legal=add(reasons,'div',null,'legal-basis');for(const law of info.laws){const item=add(legal,'article');const link=add(item,'a',law.title+' ↗');link.href=law.url;link.target='_blank';link.rel='noopener';add(item,'p',law.text);}
  add(reasons,'p','법 조문은 주의 의무를 설명하며, 표시된 비율 자체를 정하는 규정은 아닙니다. 사고 유형에 대한 프로그램의 예상이며 위반 여부나 최종 과실이 확정된 것은 아닙니다.','legal-note');
  const check=add(container,'div',null,'verdict-check');add(check,'b','추가로 확인하면 좋은 점');add(check,'p',info.check);
  if(report.recommendation?.premise_source==='user_description_unverified')add(check,'p','후방 추돌이라는 입력 설명을 전제로 계산했습니다. 충돌 상대와 진행 방향을 영상으로 검증한 결과는 아닙니다.');
  if(report.fault.ratio_change_summary)add(check,'p',report.fault.ratio_change_summary);
  if(report.fault.unknowns?.length){const more=add(check,'details');add(more,'summary','이번 분석에서 확인되지 않은 내용');const ul=add(more,'ul');for(const value of report.fault.unknowns)add(ul,'li',value);}
  scenarioDetails();
 }
 root.ClearframeReport={explain,render};
 if(typeof module!=='undefined')module.exports=root.ClearframeReport;
})(typeof window!=='undefined'?window:globalThis);
