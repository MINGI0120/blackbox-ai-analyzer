/* Streamlit component transport. Analysis still runs in the user's Python engine. */
(() => {
  let args = null, resolveReady;
  const ready = new Promise(resolve => resolveReady = resolve);
  const pending = new Map();
  let queue = Promise.resolve();
  const send = (type, extra = {}) => parent.postMessage({isStreamlitMessage:true, type, ...extra}, '*');
  const height = () => send('streamlit:setFrameHeight', {height: Math.max(760, Math.min(1000, window.screen.availHeight - 140))});
  window.addEventListener('message', event => {
    if (event.source !== parent || event.data?.type !== 'streamlit:render') return;
    args = event.data.args;
    resolveReady();
    const reply = args.reply;
    if (reply && pending.has(reply.id)) {
      const {resolve, reject, timer} = pending.get(reply.id);
      clearTimeout(timer); pending.delete(reply.id);
      send('streamlit:setComponentValue', {value:{id:crypto.randomUUID(), action:'ack'}, dataType:'json'});
      reply.error ? reject(new Error(reply.error)) : resolve(reply);
    }
  });
  function request(action, payload = {}) {
    const operation = queue.then(() => new Promise((resolve, reject) => {
      const id = crypto.randomUUID();
      const timer = setTimeout(() => {pending.delete(id);reject(new Error('연결이 지연되고 있습니다. 페이지를 다시 열어 주세요.'));}, 45000);
      pending.set(id,{resolve,reject,timer});
      send('streamlit:setComponentValue', {value:{...payload,id,action},dataType:'json'});
    }));
    queue = operation.catch(() => {});
    return operation;
  }
  const json = (value, status = 200) => new Response(JSON.stringify(value), {status,headers:{'Content-Type':'application/json'}});
  const nativeFetch = window.fetch.bind(window);
  window.fetch = async (input, options = {}) => {
    const url = new URL(typeof input === 'string' ? input : input.url, location.href);
    if (!url.pathname.startsWith('/api/')) return nativeFetch(input, options);
    await ready;
    const path = url.pathname;
    if (path === '/api/session') return json({token:'streamlit-session'});
    if (path === '/api/health') return json({service:'roadlens',model_ready:true});
    if (path === '/api/rules') return json(args.rules);
    if (path === '/api/jobs' && options.method === 'POST') {
      const form = options.body, video = form.get('video');
      if (video.size > 20 * 1024 * 1024) return json({detail:'무료 분석은 20MB 이하 영상을 사용해 주세요.'},413);
      const encoded = await new Promise((resolve,reject) => {const r=new FileReader();r.onload=()=>resolve(r.result.split(',')[1]);r.onerror=reject;r.readAsDataURL(video)});
      const reply = await request('analyze', {video:encoded,situation:form.get('situation'),rule_key:form.get('rule_key'),automatic:form.get('automatic')==='true',modifier_target:form.get('modifier_target')});
      return json({id:reply.id});
    }
    const match = path.match(/^\/api\/jobs\/([^/]+)(?:\/files\/(.+))?$/);
    if (match) {
      if (options.method === 'DELETE') {await request('delete');return json({state:'cancelled'})}
      if (match[2]) {
        const reply = await request('asset',{name:match[2]});
        return new Response(Uint8Array.from(atob(reply.data), c=>c.charCodeAt(0)), {headers:{'Content-Type':match[2].endsWith('.mp4')?'video/mp4':match[2].endsWith('.jpg')?'image/jpeg':'application/json'}});
      }
      return json(args.job?.id === match[1] ? args.job : {state:'failed',message:'결과가 만료되었습니다. 다시 분석해 주세요.'});
    }
    return json({detail:'지원하지 않는 요청입니다.'},404);
  };
  window.addEventListener('DOMContentLoaded', () => {
    document.querySelector('#engine-settings').hidden = true;
    document.querySelector('#local-guide').hidden = true;
    document.querySelector('#dropzone small').textContent = '무료 온라인 분석 · 최대 20MB · 60초 · 720p';
    const note = '분석을 시작하면 영상과 사고 설명이 Streamlit 서버로 전송됩니다. 원본은 처리 후 삭제하며, 결과는 현재 접속 세션에서만 접근할 수 있고 처리 후 15분 뒤 삭제됩니다.';
    document.querySelector('.upload-disclaimer').textContent = note;
    document.querySelector('#analysis-form > .analysis-caption:last-child').textContent = note;
    document.querySelectorAll('.faq-list details p')[1].textContent = note;
  });
  send('streamlit:componentReady', {apiVersion:1});
  height();
})();
