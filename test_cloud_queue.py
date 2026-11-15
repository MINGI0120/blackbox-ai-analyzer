import base64
import json
import threading
import time
from pathlib import Path

import pytest
import cloud_runtime as runtime


def request(name):
    return dict(id=name, video=base64.b64encode(b'test-video').decode(),
                situation='골목길 사고', rule_key='rear_end', automatic=True,
                modifier_target='none')


class ControlledJob(runtime.CloudJob):
    def __init__(self, order, failure=None):
        super().__init__()
        self.entered = threading.Event()
        self.finish = threading.Event()
        self.order = order
        self.failure = failure

    def _analyze(self, path, payload, progress, stopped, set_stage):
        self.order.append(payload['id'])
        self.entered.set()
        set_stage('영상 분석')
        while not self.finish.wait(.01):
            if stopped():
                raise InterruptedError('stopped')
        if self.failure:
            raise self.failure
        progress(.96, 'saving')
        return {'test_owner': payload['id']}


@pytest.fixture
def jobs(monkeypatch):
    monkeypatch.setattr(runtime, 'QUEUE', runtime.AnalysisQueue())
    created = []
    order = []

    def make(failure=None):
        job = ControlledJob(order, failure)
        created.append(job)
        return job

    yield make, order
    for job in created:
        job.cancel.set()
        job.finish.set()
    for job in created:
        if job.worker and job.worker.ident is not None:
            job.worker.join(3)
        job.clear()


def done(job):
    job.worker.join(3)
    assert not job.worker.is_alive()
    return job.snapshot()


def test_fifo_one_analysis_and_private_results(jobs):
    make, order = jobs
    first, second, third = make(), make(), make()
    first.start(request('one'))
    assert first.entered.wait(1)
    second.start(request('two'))
    third.start(request('three'))
    assert second.snapshot()['state'] == third.snapshot()['state'] == 'queued'
    assert not second.entered.is_set() and not third.entered.is_set()
    with pytest.raises(ValueError, match='없거나 만료'):
        second.asset('report.json')
    first.finish.set()
    assert second.entered.wait(1)
    assert not third.entered.is_set()
    second.finish.set()
    assert third.entered.wait(1)
    third.finish.set()
    assert [done(j)['state'] for j in (first, second, third)] == ['complete'] * 3
    assert order == ['one', 'two', 'three']
    for job, name in ((first, 'one'), (second, 'two'), (third, 'three')):
        assert json.loads(base64.b64decode(job.asset('report.json'))) == {'test_owner': name}
        assert not (Path(job.folder.name) / 'input.mp4').exists()


def test_cancel_waiting_job_does_not_start_or_block_next(jobs):
    make, order = jobs
    first, second, third = make(), make(), make()
    first.start(request('one'))
    assert first.entered.wait(1)
    second.start(request('two'))
    third.start(request('three'))
    second.clear()
    assert done(second)['state'] == 'cancelled'
    first.finish.set()
    assert third.entered.wait(1)
    third.finish.set()
    assert done(third)['state'] == 'complete'
    assert order == ['one', 'three']


def test_analysis_failure_releases_slot(jobs):
    make, _ = jobs
    first, second = make(ModuleNotFoundError('test dependency')), make()
    first.start(request('one'))
    assert first.entered.wait(1)
    second.start(request('two'))
    first.finish.set()
    assert done(first)['state'] == 'failed'
    assert second.entered.wait(1)
    second.finish.set()
    assert done(second)['state'] == 'complete'


def test_cleanup_failure_still_releases_slot(jobs, monkeypatch):
    make, _ = jobs
    first, second = make(), make()
    first.start(request('one'))
    assert first.entered.wait(1)
    blocked_path = Path(first.folder.name) / 'input.mp4'
    original = Path.unlink

    def fail_one(path, *args, **kwargs):
        if path == blocked_path:
            raise PermissionError('simulated locked input')
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'unlink', fail_one)
    second.start(request('two'))
    first.finish.set()
    assert done(first)['state'] == 'complete'
    assert second.entered.wait(1)
    second.finish.set()
    assert done(second)['state'] == 'complete'
    monkeypatch.setattr(Path, 'unlink', original)


def test_disconnected_job_stops_and_next_starts(jobs):
    make, _ = jobs
    first, second = make(), make()
    first.start(request('one'))
    assert first.entered.wait(1)
    second.start(request('two'))
    first.last_seen = time.monotonic() - runtime.SESSION_IDLE_SECONDS - 1
    first.worker.join(2)  # Inspecting snapshot would renew the session heartbeat.
    assert first.data['state'] == 'cancelled'
    assert '연결' in first.data['message']
    assert second.entered.wait(1)
    second.finish.set()
    assert done(second)['state'] == 'complete'


def test_analysis_timeout_releases_slot(jobs, monkeypatch):
    monkeypatch.setattr(runtime, 'ANALYSIS_SECONDS', .05)
    make, _ = jobs
    first = make()
    first.start(request('one'))
    assert first.entered.wait(1)
    state = done(first)
    assert state['state'] == 'failed' and '분석 시간이' in state['message']
    assert runtime.QUEUE.entries == []


def test_wait_timeout_releases_only_waiting_job(jobs, monkeypatch):
    monkeypatch.setattr(runtime, 'QUEUE_WAIT_SECONDS', .05)
    make, _ = jobs
    first, second = make(), make()
    first.start(request('one'))
    assert first.entered.wait(1)
    second.start(request('two'))
    state = done(second)
    assert state['state'] == 'failed' and '대기 시간이' in state['message']
    assert not second.entered.is_set()
    assert len(runtime.QUEUE.entries) == 1
    first.finish.set()
    assert done(first)['state'] == 'complete'


def test_bounded_capacity_and_duplicate_request(jobs):
    make, _ = jobs
    accepted = [make() for _ in range(4)]
    for index, job in enumerate(accepted):
        job.start(request(str(index)))
    with pytest.raises(ValueError, match='이미 분석 중'):
        accepted[0].start(request('duplicate'))
    with pytest.raises(ValueError, match='대기열이 가득'):
        make().start(request('overflow'))
    assert len(runtime.QUEUE.entries) == 4


def test_thread_launch_failure_does_not_leak_queue(jobs, monkeypatch):
    make, _ = jobs
    first = make()
    original = threading.Thread.start
    with monkeypatch.context() as patch:
        patch.setattr(threading.Thread, 'start', lambda _: (_ for _ in ()).throw(RuntimeError('thread failed')))
        with pytest.raises(RuntimeError):
            first.start(request('one'))
    assert runtime.QUEUE.entries == [] and first.folder is None
    first.start(request('retry'))
    assert first.entered.wait(1)
    first.finish.set()
    assert done(first)['state'] == 'complete'


def test_invalid_video_never_reserves_slot(jobs):
    make, _ = jobs
    payload = request('empty')
    payload['video'] = ''
    with pytest.raises(ValueError):
        make().start(payload)
    assert runtime.QUEUE.entries == []
