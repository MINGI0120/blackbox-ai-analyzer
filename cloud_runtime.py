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
QUEUE_WAIT_SECONDS = 600
ANALYSIS_SECONDS = 600
SESSION_IDLE_SECONDS = 180


class AnalysisQueue:
    """Bounded FIFO; queued jobs never load a model or expose another result."""
    def __init__(self, capacity=4):
        self.condition = threading.Condition()
        self.entries = []
        self.active = None
        self.capacity = capacity

    def submit(self, ticket):
        with self.condition:
            if len(self.entries) >= self.capacity:
                raise ValueError('분석 대기열이 가득 찼습니다. 잠시 후 다시 시도해 주세요.')
            self.entries.append(ticket)
            self.condition.notify_all()

    def acquire(self, ticket, stopped, waiting):
        while not stopped():
            with self.condition:
                if ticket not in self.entries:
                    return False
                ahead = self.entries.index(ticket)
                if ahead == 0 and self.active is None:
                    self.active = ticket
                    return True
                self.condition.wait(timeout=.25)
            waiting(ahead)
        return False

    def release(self, ticket):
        with self.condition:
            if self.active == ticket:
                self.active = None
            if ticket in self.entries:
                self.entries.remove(ticket)
            self.condition.notify_all()


QUEUE = AnalysisQueue()
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
        self.last_seen = time.monotonic()
        self.worker = None
        # Release work on the exact queue instance that accepted it.
        self.queue = QUEUE

    def snapshot(self):
        with self.lock:
            self.last_seen = time.monotonic()
            return dict(self.data)

    def start(self, request):
        with self.lock:
            self._start(request)

    def _start(self, request):
        if self.snapshot().get('state') in ('running', 'queued'):
            raise ValueError('이미 분석 중입니다.')
        if self.worker and self.worker.is_alive():
            raise ValueError('이전 분석을 정리하고 있습니다. 잠시 후 다시 시도해 주세요.')
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
        ticket = uuid.uuid4().hex
        self.queue.submit(ticket)
        try:
            self.clear()
            self.folder = tempfile.TemporaryDirectory(prefix='roadlens-cloud-')
            self.id = request['id']
            self.cancel = threading.Event()
            path = Path(self.folder.name) / 'input.mp4'
            path.write_bytes(raw)
            self.last_seen = time.monotonic()
            self.data = {'id': self.id, 'state': 'queued', 'progress': 0, 'message': '분석을 접수했습니다. 순서가 되면 자동으로 시작합니다.'}
            payload = request.copy()
            payload.pop('video', None)
            self.worker = threading.Thread(target=self.run, args=(path, payload, ticket), daemon=True)
            self.worker.start()
        except BaseException:
            self.queue.release(ticket)
            self.data = {}
            if self.folder:
                try:
                    self.folder.cleanup()
                except OSError:
                    logging.getLogger(__name__).warning('Could not clean up rejected job files.')
            self.folder = None
            raise

    def run(self, path, request, ticket):
        deadline = time.monotonic() + QUEUE_WAIT_SECONDS
        stage = '분석 대기'
        reason = None
        result = None
        final = {}
        folder = self.folder

        def stopped():
            nonlocal reason
            now = time.monotonic()
            if self.cancel.is_set():
                reason = 'cancelled'
            elif now - self.last_seen > SESSION_IDLE_SECONDS:
                reason = 'disconnected'
            elif now > deadline:
                reason = 'queue_timeout' if stage == '분석 대기' else 'timeout'
            return reason is not None

        def waiting(ahead):
            with self.lock:
                self.data.update(state='queued', message=f'분석 대기 중 · 앞에 {ahead}개 작업이 있습니다. 순서가 되면 자동으로 시작합니다.')

        def set_stage(value):
            nonlocal stage
            stage = value

        def progress(value, message):
            set_stage('결과 영상 저장' if value >= .96 else '영상 프레임 분석')
            if stopped():
                raise InterruptedError('Analysis stopped')
            with self.lock:
                self.data.update(state='running', progress=value, message=message)

        try:
            if not self.queue.acquire(ticket, stopped, waiting) or stopped():
                raise InterruptedError('Analysis stopped while waiting')
            deadline = time.monotonic() + ANALYSIS_SECONDS
            set_stage('분석 환경 불러오기')
            with self.lock:
                self.data.update(state='running', message='분석 모델을 준비하고 있습니다.')
            logging.getLogger(__name__).info('Analysis started: %s', ticket[:8])
            result = self._analyze(path, request, progress, stopped, set_stage)
            if stopped():
                raise InterruptedError('Analysis stopped')
            set_stage('분석 보고서 저장')
            (path.parent / 'report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            final = {'state': 'complete', 'progress': 1, 'message': '분석 완료', 'result': result}
        except Exception as exc:
            code = uuid.uuid4().hex[:8]
            stopped()
            if not reason:
                record_failure(exc, stage, code)
            messages = {
                'cancelled': '분석을 취소했습니다.',
                'disconnected': '화면 연결이 3분 이상 끊겨 분석을 종료했습니다. 영상을 다시 선택해 주세요.',
                'queue_timeout': '대기 시간이 10분을 초과했습니다. 잠시 후 다시 시도해 주세요.',
                'timeout': '분석 시간이 10분을 초과해 종료했습니다. 더 짧은 영상으로 시도해 주세요.',
            }
            final = {'state': 'cancelled' if reason in ('cancelled', 'disconnected') else 'failed',
                     'message': messages.get(reason) or failure_message(exc, stage, code),
                     'error_code': code, 'error_type': type(exc).__name__, 'error_stage': stage}
        finally:
            try:
                try:
                    path.unlink(missing_ok=True)
                    if final.get('state') != 'complete' and folder:
                        folder.cleanup()
                except OSError:
                    logging.getLogger(__name__).warning('Could not clean up analysis files: %s', ticket[:8])
            finally:
                self.queue.release(ticket)
                with self.lock:
                    self.data.update(final or {'state': 'failed', 'message': '분석 작업이 중단되었습니다. 다시 시도해 주세요.'})
                logging.getLogger(__name__).info('Analysis finished: %s (%s)', ticket[:8], self.data.get('state'))
            timer = threading.Timer(900, self.expire, args=(request['id'],))
            timer.daemon = True
            timer.start()

    def _analyze(self, path, request, progress, stopped, set_stage):
        import cv2
        import torch
        torch.set_num_threads(2)
        cv2.setNumThreads(2)
        set_stage('영상 열기')
        cap = cv2.VideoCapture(str(path))
        try:
            w, h, fps, count = [cap.get(p) for p in (cv2.CAP_PROP_FRAME_WIDTH, cv2.CAP_PROP_FRAME_HEIGHT, cv2.CAP_PROP_FPS, cv2.CAP_PROP_FRAME_COUNT)]
        finally:
            cap.release()
        if not all(math.isfinite(v) and v > 0 for v in (w, h, fps, count)) or w > 1280 or h > 720 or count / fps > 60 or count > 1800:
            raise ValueError('무료 분석은 720p 이하, 60초·1,800프레임 이내 영상으로 이용해 주세요.')
        if stopped():
            raise InterruptedError('Analysis stopped')
        set_stage('차량 탐지 모델 준비')
        from ultralytics import YOLO
        model_path = Path(os.environ.get('ROADLENS_MODEL', str(Path(tempfile.gettempdir()) / 'roadlens-model' / 'yolo11n.pt')))
        with MODEL_LOCK:
            if not model_path.is_file():
                model_path.parent.mkdir(parents=True, exist_ok=True)
                YOLO(str(model_path))
        if stopped():
            raise InterruptedError('Analysis stopped')
        set_stage('분석 코드 불러오기')
        from analysis_engine import analyze_video
        set_stage('영상 분석')
        return analyze_video(path, path.parent, request['situation'], request['rule_key'], request.get('automatic') is True,
                             None if request['modifier_target'] == 'none' else request['modifier_target'],
                             progress, stopped, model_path)

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

