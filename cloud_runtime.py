"""Per-browser jobs; no public API or shared result directory."""
import base64
import json
import math
import os
import tempfile
import threading
import time
import logging
import traceback
import uuid
from pathlib import Path

MAX_BYTES = 20 * 1024 * 1024
GATE = threading.BoundedSemaphore(1)
MODEL_LOCK = threading.Lock()
os.environ.setdefault('YOLO_CONFIG_DIR', str(Path(tempfile.gettempdir()) / 'roadlens-yolo'))


def failure_message(exc, stage, code):
    if isinstance(exc, ValueError):
        return str(exc)
    if isinstance(exc, ModuleNotFoundError):
        detail = '실행 환경에 필요한 분석 패키지가 없습니다.'
    elif isinstance(exc, ImportError):
        detail = '분석 패키지 또는 코드의 버전이 맞지 않습니다.'
    elif isinstance(exc, PermissionError):
        detail = '분석 파일이나 실행 프로그램에 접근할 권한이 없습니다.'
    elif isinstance(exc, MemoryError):
        detail = '분석에 사용할 메모리가 부족합니다.'
    else:
        detail = '분석 프로그램에서 오류가 발생했습니다.'
    return f'{stage} 단계: {detail} 오류 종류: {type(exc).__name__}, 확인 코드: {code}. 실행 터미널의 오류 기록을 확인해 주세요.'


def record_failure(exc, stage, code):
    # No video or request payload is included. Full traceback stays on server.
    detail = f'[{code}] {stage}\n' + ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    logging.getLogger(__name__).error(detail)
    try:
        folder = Path(os.environ.get('ROADLENS_LOG_DIR', str(Path(tempfile.gettempdir()) / 'roadlens-errors')))
        folder.mkdir(parents=True, exist_ok=True)
        # One rolling diagnostic file avoids accumulating user data indefinitely.
        (folder / 'last-error.log').write_text(detail, encoding='utf-8')
    except OSError:
        logging.getLogger(__name__).warning('Could not save diagnostic file; see terminal output.')

class CloudJob:
    def __init__(self):
        self.lock = threading.RLock()
        self.cancel = threading.Event()
        self.data = {}
        self.folder = None
        self.id = None

    def snapshot(self):
        with self.lock:
            return dict(self.data)

    def start(self, request):
        if self.snapshot().get('state') in ('running', 'queued'):
            raise ValueError('이미 분석 중입니다.')
        encoded = request.get('video', '')
        if not isinstance(encoded, str) or len(encoded) > (MAX_BYTES + 2) // 3 * 4:
            raise ValueError('무료 분석은 20MB 이하 영상만 지원합니다.')
        raw = base64.b64decode(encoded, validate=True)
        if not 0 < len(raw) <= MAX_BYTES:
            raise ValueError('빈 영상이거나 20MB를 초과했습니다.')
        situation = request.get('situation', '').strip()
        from fault_rules import FAULT_RULES
        if not 0 < len(situation) <= 10000 or request.get('rule_key') not in FAULT_RULES:
            raise ValueError('사고 설명과 사고 유형을 확인해 주세요.')
        if request.get('modifier_target') not in ('none', 'A', 'B'):
            raise ValueError('잘못된 차량 선택입니다.')
        if not GATE.acquire(blocking=False):
            raise ValueError('다른 사용자가 분석 중입니다. 잠시 후 다시 시도해 주세요.')
        try:
            self.clear()
            self.folder = tempfile.TemporaryDirectory(prefix='roadlens-cloud-')
            self.id = request['id']
            self.cancel = threading.Event()
            path = Path(self.folder.name) / 'input.mp4'
            path.write_bytes(raw)
            self.data = {'id': self.id, 'state': 'queued', 'progress': 0, 'message': '분석 모델을 준비하고 있습니다.'}
            threading.Thread(target=self.run, args=(path, request.copy()), daemon=True).start()
        except BaseException:
            GATE.release()
            raise

    def run(self, path, request):
        request.pop('video', None)
        deadline = time.monotonic() + 600
        stage = '분석 환경 불러오기'
        try:
            import cv2
            import torch
            torch.set_num_threads(2)
            cv2.setNumThreads(2)
            stage = '영상 열기'
            cap = cv2.VideoCapture(str(path))
            w, h, fps, count = [cap.get(p) for p in (cv2.CAP_PROP_FRAME_WIDTH, cv2.CAP_PROP_FRAME_HEIGHT, cv2.CAP_PROP_FPS, cv2.CAP_PROP_FRAME_COUNT)]
            cap.release()
            if not all(math.isfinite(v) and v > 0 for v in (w, h, fps, count)) or w > 1280 or h > 720 or count / fps > 60 or count > 1800:
                raise ValueError('무료 분석은 720p 이하, 60초·1,800프레임 이내 영상으로 이용해 주세요.')
            stage = '차량 탐지 모델 준비'
            from ultralytics import YOLO
            model_path = Path(os.environ.get('ROADLENS_MODEL', str(Path(tempfile.gettempdir()) / 'roadlens-model' / 'yolo11n.pt')))
            with MODEL_LOCK:
                if not model_path.is_file():
                    model_path.parent.mkdir(parents=True, exist_ok=True)
                    YOLO(str(model_path))
            stage = '분석 코드 불러오기'
            from analysis_engine import analyze_video
            def progress(value, message):
                nonlocal stage
                stage = '결과 영상 저장' if value >= .96 else '영상 프레임 분석'
                with self.lock:
                    self.data.update(state='running', progress=value, message=message)
            stage = '영상 분석'
            result = analyze_video(path, path.parent, request['situation'], request['rule_key'], request.get('automatic') is True,
                                   None if request['modifier_target'] == 'none' else request['modifier_target'],
                                   progress, lambda: self.cancel.is_set() or time.monotonic() > deadline, model_path)
            stage = '분석 보고서 저장'
            (path.parent / 'report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            with self.lock:
                self.data.update(state='complete', progress=1, message='분석 완료', result=result)
        except Exception as exc:
            code = uuid.uuid4().hex[:8]
            if not self.cancel.is_set():
                record_failure(exc, stage, code)
            with self.lock:
                self.data.update(state='cancelled' if self.cancel.is_set() else 'failed',
                                 message='분석을 취소했습니다.' if self.cancel.is_set() else failure_message(exc, stage, code),
                                 error_code=code, error_type=type(exc).__name__, error_stage=stage)
            if self.folder:
                self.folder.cleanup()
        finally:
            path.unlink(missing_ok=True)
            GATE.release()
            timer = threading.Timer(900, self.expire, args=(request['id'],))
            timer.daemon = True
            timer.start()

    def asset(self, name):
        with self.lock:
            if self.data.get('state') != 'complete' or name not in ('report.json', 'analyzed.mp4', 'risk.jpg') or not self.folder:
                raise ValueError('분석 결과가 없거나 만료되었습니다.')
            path = Path(self.folder.name) / name
            if not path.is_file() or path.stat().st_size > 30 * 1024 * 1024:
                raise ValueError('파일이 없거나 무료 전송 한도 30MB를 초과했습니다.')
            return base64.b64encode(path.read_bytes()).decode('ascii')

    def expire(self, job_id):
        with self.lock:
            if self.id == job_id:
                self.clear()

    def clear(self):
        with self.lock:
            self.cancel.set()
            if self.data.get('state') in ('running', 'queued'):
                return
            if self.folder:
                self.folder.cleanup()
            self.folder = None
            self.data = {}

