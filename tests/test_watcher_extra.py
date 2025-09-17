import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

import imgc.watcher as watcher_mod
from imgc.watcher import ImageHandler, process_existing, start_watch


def test_process_existing_with_workers(tmp_path):
    files = []
    for i in range(4):
        p = tmp_path / f'{i}.jpg'
        p.write_bytes(b'data')
        files.append(p)

    calls = []

    class MockComp:
        def compress(self, p):
            calls.append(p.name)
            return {'new': 1}

    handler = ImageHandler(compressor=MockComp(), stable_seconds=0.01, new_delay=0, cooldown=0, compress_timeout=0)
    handler.workers = 2
    process_existing(tmp_path, handler)
    assert set(calls) == {f'{i}.jpg' for i in range(4)}


def test_on_created_timeout_logs(monkeypatch, tmp_path, caplog):
    p = tmp_path / 'late.jpg'
    p.write_bytes(b'data')

    called = {'n': 0}

    class SlowComp:
        def compress(self, path):
            called['n'] += 1
            time.sleep(0.5)
            return {'new': 1}

    handler = ImageHandler(compressor=SlowComp(), stable_seconds=0.0, new_delay=0, cooldown=0, compress_timeout=0.01)
    ev = SimpleNamespace(is_directory=False, src_path=str(p))
    # ensure wait_for_stable_file returns True quickly
    monkeypatch.setattr(watcher_mod, 'wait_for_stable_file', lambda *a, **k: True)
    caplog.clear()
    caplog.set_level('INFO')
    handler.on_created(ev)
    # Compression should have timed out and logged a warning
    assert any('timed out' in r.message or 'timed out or failed' in r.message for r in caplog.records)


def test_start_watch_mirrors_lifecycle(monkeypatch, tmp_path, caplog):
    # Provide a dummy Observer that records start/stop
    observers = []

    class DummyObserver:
        def __init__(self):
            self.started = False
            observers.append(self)
        def schedule(self, handler, path, recursive=True):
            self.scheduled = (handler, path, recursive)
        def start(self):
            self.started = True
        def stop(self):
            self.started = False
        def join(self, timeout=None):
            return

    # Replace Observer used inside module with factory that records instances
    monkeypatch.setattr(watcher_mod, 'Observer', DummyObserver)

    # Replace signal.signal inside watcher module with a no-op
    def fake_signal(sig, handler):
        pass

    monkeypatch.setattr(watcher_mod.signal, 'signal', fake_signal)

    # We don't need to patch Thread - we'll let the background thread run normally

    # Use a no-op compressor
    class NoopComp:
        def compress(self, p):
            return {'new': 1}

    # Create our own stop event that we can control
    stop_event = threading.Event()

    # Run start_watch in a thread so we can set the event. Use a finished
    # flag written by the runner to avoid checking Thread.is_alive().
    finished = {'done': False}

    def runner():
        try:
            start_watch(tmp_path, NoopComp(), workers=1, file_timeout=0.0, stable_seconds=0.0, new_delay=0.0, compress_timeout=0, stop_event=stop_event)
        finally:
            finished['done'] = True

    t = threading.Thread(target=runner, daemon=True)
    caplog.clear()
    t.start()
    
    # Wait until the DummyObserver has been created and scheduled by
    # start_watch. Poll to avoid races with the watcher startup.
    deadline = time.time() + 1.0
    while time.time() < deadline:
        if observers and getattr(observers[0], 'scheduled', None):
            break
        time.sleep(0.01)

    # Give a short time for start_watch to get to the wait loop
    time.sleep(0.1)
    
    # Now set the event to signal shutdown
    stop_event.set()
    
    # Wait up to 3s for the runner to mark finished
    deadline = time.time() + 3
    while time.time() < deadline and not finished['done']:
        time.sleep(0.05)
    
    assert finished['done'] is True