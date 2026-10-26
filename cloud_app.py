from pathlib import Path
import tempfile
import shutil
import hashlib
import streamlit as st
import streamlit.components.v1 as components
from streamlit import config as streamlit_config
from cloud_runtime import CloudJob
from fault_rules import FAULT_RULES

# Frequent fragment reruns can reference a ForwardMsg already evicted by the
# browser (Cached ForwardMsg MISS). Send complete messages instead. Keep the
# threshold above the transport limit so no valid message becomes cacheable.
# Set this before rendering, including when launched without a config.toml.
streamlit_config.set_option(
    'global.minCachedMessageSize',
    int(streamlit_config.get_option('server.maxMessageSize')) * 1024 * 1024 + 1,
)

ASSET_NAMES = ('robot-scene.html', 'index.html', 'app.js', 'flow.js', 'analysis.js', 'cloud-bridge.js', 'report-view.js', 'style.css', 'flow.css', 'analysis.css', 'refinements.css')
ROOT = Path(__file__).parent
ASSET_SOURCE = ROOT / 'frontend' if (ROOT / 'frontend').is_dir() else ROOT
ASSET_VERSION = hashlib.sha256(b''.join((ASSET_SOURCE / name).read_bytes() for name in ASSET_NAMES)).hexdigest()

@st.cache_resource
def component_assets(asset_version):
    target = tempfile.TemporaryDirectory(prefix='roadlens-ui-')
    for name in ASSET_NAMES:
        shutil.copyfile(ASSET_SOURCE / name, Path(target.name) / name)
    return target

screen = components.declare_component('roadlens_screen', path=component_assets(ASSET_VERSION).name)
@st.fragment(run_every=1)
def interface():
    job = st.session_state.cloud_job
    event = screen(rules=[{'key': key, **value} for key, value in FAULT_RULES.items()], job=job.snapshot(), reply=st.session_state.reply, default=None, key='roadlens')
    if not isinstance(event, dict) or not isinstance(event.get('id'), str) or event['id'] == st.session_state.last_event:
        return
    st.session_state.last_event = event['id']
    reply = {'id': event['id']}
    try:
        action = event.get('action')
        if action == 'analyze':
            job.start(event)
        elif action == 'delete':
            job.clear()
        elif action == 'asset':
            reply['data'] = job.asset(event.get('name'))
        elif action == 'ack':
            st.session_state.reply = None
            return
        else:
            raise ValueError('지원하지 않는 요청입니다.')
    except Exception as exc:
        reply['error'] = str(exc) if isinstance(exc, ValueError) else '요청을 처리하지 못했습니다. 다시 시도해 주세요.'
    st.session_state.reply = reply

def main():
    st.set_page_config(page_title='블랙박스 AI 과실비율 탐지', page_icon='🚗', layout='wide', initial_sidebar_state='collapsed')
    st.markdown('<style>.block-container{padding:0;max-width:none}header[data-testid="stHeader"]{display:none}.stApp{background:#101211}[data-testid="stVerticalBlock"]{gap:0}</style>', unsafe_allow_html=True)
    if 'cloud_job' not in st.session_state:
        st.session_state.cloud_job = CloudJob()
        st.session_state.last_event = None
        st.session_state.reply = None
    
    interface()

if __name__ == "__main__":
    main()
