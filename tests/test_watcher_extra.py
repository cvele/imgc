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


def test_start_watch_process_existing_flag(monkeypatch, tmp_path, caplog):
    """Test that process_existing flag controls whether existing files are processed."""
    # Set logging level to capture info messages
    caplog.set_level('INFO')
    # Create some test images
    test_files = []
    for i in range(3):
        img_path = tmp_path / f'test{i}.jpg'
        img_path.write_bytes(b'fake_image_data')
        test_files.append(img_path)

    # Mock Observer
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

    monkeypatch.setattr(watcher_mod, 'Observer', DummyObserver)
    monkeypatch.setattr(watcher_mod.signal, 'signal', lambda sig, handler: None)

    # Mock process_existing to track if it was called
    process_existing_called = {'count': 0}
    original_process_existing = watcher_mod.process_existing
    
    def mock_process_existing(root, handler):
        process_existing_called['count'] += 1
        # Don't actually process, just record the call
    monkeypatch.setattr(watcher_mod, 'process_existing', mock_process_existing)

    # No-op compressor
    class NoopComp:
        def compress(self, p):
            return {'new': 1}

    stop_event = threading.Event()

    # Test 1: Default behavior (process_existing=False)
    finished = {'done': False}
    
    def runner_watch_only():
        try:
            start_watch(tmp_path, NoopComp(), scan_existing=False, stop_event=stop_event)
        finally:
            finished['done'] = True

    t1 = threading.Thread(target=runner_watch_only, daemon=True)
    caplog.clear()
    t1.start()
    
    # Wait for observer to start
    deadline = time.time() + 1.0
    while time.time() < deadline:
        if observers and getattr(observers[0], 'scheduled', None):
            break
        time.sleep(0.01)
    
    # Give a moment for any background processing
    time.sleep(0.1)
    
    # Stop the watcher
    stop_event.set()
    
    # Wait for completion
    deadline = time.time() + 2
    while time.time() < deadline and not finished['done']:
        time.sleep(0.05)
    
    # Verify process_existing was NOT called (watch-only mode)
    assert process_existing_called['count'] == 0
    # Check for the log message (it might be in different log levels)
    log_messages = [record.message for record in caplog.records]
    watch_only_logged = any('Watch-only mode' in msg for msg in log_messages)
    assert watch_only_logged, f"Expected watch-only mode message in logs. Got: {log_messages}"
    assert finished['done'] is True

    # Reset for test 2
    process_existing_called['count'] = 0
    finished['done'] = False
    stop_event.clear()
    observers.clear()
    
    # Test 2: With process_existing=True
    def runner_process_existing():
        try:
            start_watch(tmp_path, NoopComp(), scan_existing=True, stop_event=stop_event)
        finally:
            finished['done'] = True

    t2 = threading.Thread(target=runner_process_existing, daemon=True)
    caplog.clear()
    t2.start()
    
    # Wait for observer to start
    deadline = time.time() + 1.0
    while time.time() < deadline:
        if observers and getattr(observers[0], 'scheduled', None):
            break
        time.sleep(0.01)
    
    # Give time for background processing to start
    time.sleep(0.1)
    
    # Stop the watcher
    stop_event.set()
    
    # Wait for completion
    deadline = time.time() + 2
    while time.time() < deadline and not finished['done']:
        time.sleep(0.05)
    
    # Verify process_existing WAS called
    assert process_existing_called['count'] == 1
    # Check for the log message (it might be in different log levels)
    log_messages = [record.message for record in caplog.records]
    processing_enabled_logged = any('Processing existing images enabled' in msg for msg in log_messages)
    assert processing_enabled_logged, f"Expected processing enabled message in logs. Got: {log_messages}"
    assert finished['done'] is True


def test_environment_variable_parsing_functions():
    """Test the actual environment variable parsing functions from main.py."""
    import os
    from main import _env_bool, _env_str, _env_int, _env_float
    
    # Test boolean parsing with various values
    bool_test_cases = [
        ('true', True),
        ('True', True),
        ('TRUE', True),
        ('1', True),
        ('yes', True),
        ('YES', True),
        ('on', True),
        ('ON', True),
        ('false', False),
        ('False', False),
        ('FALSE', False),
        ('0', False),
        ('no', False),
        ('NO', False),
        ('off', False),
        ('OFF', False),
        ('', False),
        ('random', False),
    ]
    
    for env_value, expected_bool in bool_test_cases:
        # Set environment variable
        original_value = os.environ.get('TEST_BOOL')
        try:
            os.environ['TEST_BOOL'] = env_value
            result = _env_bool('TEST_BOOL', False)
            assert result == expected_bool, f"_env_bool with '{env_value}' should return {expected_bool}, got {result}"
        finally:
            # Restore original environment
            if original_value is None:
                os.environ.pop('TEST_BOOL', None)
            else:
                os.environ['TEST_BOOL'] = original_value
    
    # Test string parsing
    original_value = os.environ.get('TEST_STR')
    try:
        os.environ['TEST_STR'] = 'test_value'
        assert _env_str('TEST_STR', 'default') == 'test_value'
        assert _env_str('NONEXISTENT', 'default') == 'default'
    finally:
        if original_value is None:
            os.environ.pop('TEST_STR', None)
        else:
            os.environ['TEST_STR'] = original_value
    
    # Test integer parsing
    original_value = os.environ.get('TEST_INT')
    try:
        os.environ['TEST_INT'] = '42'
        assert _env_int('TEST_INT', 0) == 42
        assert _env_int('NONEXISTENT', 10) == 10
        
        # Test empty string handling
        os.environ['TEST_INT'] = ''
        assert _env_int('TEST_INT', 5) == 5
    finally:
        if original_value is None:
            os.environ.pop('TEST_INT', None)
        else:
            os.environ['TEST_INT'] = original_value
    
    # Test float parsing
    original_value = os.environ.get('TEST_FLOAT')
    try:
        os.environ['TEST_FLOAT'] = '3.14'
        assert _env_float('TEST_FLOAT', 0.0) == 3.14
        assert _env_float('NONEXISTENT', 2.5) == 2.5
        
        # Test empty string handling
        os.environ['TEST_FLOAT'] = ''
        assert _env_float('TEST_FLOAT', 1.5) == 1.5
    finally:
        if original_value is None:
            os.environ.pop('TEST_FLOAT', None)
        else:
            os.environ['TEST_FLOAT'] = original_value