// Keep every screen mounted so local video and notes survive navigation.
const main=document.querySelector('main');
document.body.classList.add('screen-app');
document.querySelector('.hero').id='home';
const review=document.createElement('section');
review.id='review';review.className='section review-screen';
review.innerHTML='<div class="review-heading"><div><div class="eyebrow muted">YOUR RECORD, FRAME BY FRAME</div><h2>영상을 보며 상황을 알려주세요.</h2></div><span class="review-badge">03 / REVIEW</span></div><div class="review-content upload-card"></div>';
main.append(review);
review.querySelector('.review-content').append(document.querySelector('#video-work'));
const statusNode=document.querySelector('#file-status');
review.querySelector('.review-content').append(statusNode);
const uploadStatus=document.createElement('p');uploadStatus.id='upload-status';uploadStatus.setAttribute('role','status');document.querySelector('.upload-card').append(uploadStatus);
new MutationObserver(()=>{uploadStatus.textContent=statusNode.textContent}).observe(statusNode,{childList:true,characterData:true,subtree:true});
document.querySelector('.workspace h2').innerHTML='당신의 기록을<br>불러오세요.';
document.querySelector('.workspace .eyebrow').textContent='02 — SELECT YOUR VIDEO';
const resume=document.createElement('button');resume.className='text-button resume';resume.textContent='선택한 영상으로 돌아가기 →';resume.hidden=true;resume.onclick=()=>navigate('review');document.querySelector('.upload-card').append(resume);
const screens=[...main.querySelectorAll(':scope > section')].filter(s=>s.id);
main.querySelector('.ticker').hidden=true;main.querySelector('.closing').hidden=true;
const bar=document.createElement('div');bar.className='screen-bar';bar.innerHTML='<button class="back-screen">← 이전 화면</button><div class="screen-steps" aria-label="진행 단계"><button data-go="home">01 <span>소개</span></button><i></i><button data-go="workspace">02 <span>영상 선택</span></button><i></i><button data-go="review">03 <span>영상 검토</span></button></div><span class="screen-counter"></span>';main.before(bar);
let active='home',transitionId=0;
const names={home:'소개',workspace:'영상 선택',review:'영상 검토',experience:'분석 미리보기',process:'이용 방법',questions:'자주 묻는 질문'};
const previous={home:'home',workspace:'home',review:'workspace',experience:'home',process:'home',questions:'home'};
function navigate(id,{historyMode='push',initial=false}={}){
 if(!names[id])id='home';if(id==='review'&&!video.src)id='workspace';
 if(id===active&&!initial)return;
 const old=document.getElementById(active),next=document.getElementById(id),token=++transitionId;
 const backwards=id===previous[active];active=id;
 if(id!=='review')video.pause();
 if(historyMode==='push')history.pushState({screen:id},'',id==='home'?'#home':'#'+id);
 if(historyMode==='replace')history.replaceState({screen:id},'','#'+id);
 document.title=names[id]+' — 블랙박스 AI 과실비율 탐지';
 screens.forEach(s=>{s.getAnimations().forEach(a=>a.cancel());s.hidden=s!==next;s.inert=s!==next;});
 next.scrollTop=0;
 bar.querySelector('.back-screen').disabled=id==='home';
 bar.querySelector('.screen-counter').textContent=names[id];
 document.querySelectorAll('[data-go]').forEach(b=>{b.toggleAttribute('aria-current',b.dataset.go===id);b.disabled=b.dataset.go==='review'&&!video.src});
 document.querySelectorAll('header nav a').forEach(a=>{if(a.hash==='#'+id)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current')});
 if(!initial&&!matchMedia('(prefers-reduced-motion: reduce)').matches){
  next.animate([{opacity:0,transform:`translateX(${backwards?'-':'+'}28px)`},{opacity:1,transform:'translateX(0)'}],{duration:420,easing:'cubic-bezier(.22,1,.36,1)'});
 }
 if(!initial){const heading=next.querySelector('h1,h2');heading.tabIndex=-1;heading.focus({preventScroll:true});}
}
document.addEventListener('click',e=>{const a=e.target.closest('a[href^="#"]');if(!a)return;e.preventDefault();navigate(a.hash.slice(1)||'home');});
document.querySelectorAll('[data-go]').forEach(b=>b.onclick=()=>navigate(b.dataset.go));
bar.querySelector('.back-screen').onclick=()=>navigate(previous[active]);
document.querySelector('#sample-start').onclick=()=>navigate('experience');
for(const id of ['experience','process','questions']){const actions=document.createElement('div');actions.className='screen-next';actions.innerHTML='<button class="button primary">내 영상 살펴보기 ↗</button>';actions.firstChild.onclick=()=>navigate('workspace');document.getElementById(id).append(actions);}
window.addEventListener('popstate',()=>navigate(location.hash.slice(1)||'home',{historyMode:'none'}));
const originalLoadVideo=loadVideo;
loadVideo=function(f){const accepted=originalLoadVideo(f);if(accepted){zone.hidden=false;resume.hidden=false;navigate('review');}return accepted;};
navigate('home',{initial:true,historyMode:'replace'});
