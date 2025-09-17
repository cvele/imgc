import os
import time
import pathlib
from types import SimpleNamespace
from pathlib import Path

import pytest

from imgc.watcher import is_image, ImageHandler, wait_for_stable_file, process_existing


def test_is_image():
    assert is_image(Path('foo.jpg'))
    assert is_image(Path('bar.PNG'))
    assert not is_image(Path('doc.txt'))


def test_should_process_cooldown(tmp_path):
    # Use handler directly to test _should_process
    handler = ImageHandler(compressor=None, stable_seconds=0.1, new_delay=0, cooldown=1.0, compress_timeout=0)
    p = tmp_path / 'a.jpg'
    p.write_bytes(b'1')
    assert handler._should_process(p) is True
    # Immediately calling again should be False due to cooldown
    assert handler._should_process(p) is False


def test_process_existing_calls_compressor(tmp_path, monkeypatch):
    # Create some files: two images and a text file
    img1 = tmp_path / 'one.jpg'
    img2 = tmp_path / 'two.png'
    other = tmp_path / 'readme.txt'
    img1.write_bytes(b'data')
    img2.write_bytes(b'data')
    other.write_text('hello')

    calls = []

    class MockComp:
        def compress(self, p):
            calls.append(str(p.name))
            return {'new': 1}

    handler = ImageHandler(compressor=MockComp(), stable_seconds=0.01, new_delay=0, cooldown=0, compress_timeout=0)
    # set no workers
    handler.workers = 1
    process_existing(tmp_path, handler)
    # compressor should be called for two image files (order may vary)
    assert set(calls) == {'one.jpg', 'two.png'}


def test_on_created_handles_event_and_skips_non_images(tmp_path, monkeypatch):
    p = tmp_path / 'new.jpg'
    p.write_bytes(b'abc')

    called = {'n': 0}

    class MockComp:
        def compress(self, path):
            called['n'] += 1
            return {'new': 1}

    handler = ImageHandler(compressor=MockComp(), stable_seconds=0.01, new_delay=0, cooldown=0, compress_timeout=0)

    # Non-image event should be ignored
    ev = SimpleNamespace(is_directory=False, src_path=str(tmp_path / 'file.txt'))
    handler.on_created(ev)
    assert called['n'] == 0

    # Image event should call compress
    ev2 = SimpleNamespace(is_directory=False, src_path=str(p))
    # monkeypatch wait_for_stable_file to always return True
    monkeypatch.setattr('imgc.watcher.wait_for_stable_file', lambda *a, **k: True)
    handler.on_created(ev2)
    assert called['n'] == 1


def test_wait_for_stable_file_monkeypatched(tmp_path, monkeypatch):
    p = tmp_path / 'f.jpg'
    p.write_bytes(b'x')

    # simulate Path.stat returning different sizes then stable
    orig_stat = pathlib.Path.stat
    sizes = {str(p): [10, 20, 20, 20]}

    def fake_stat(self):
        key = str(self)
        if key in sizes:
            val = sizes[key].pop(0)
            class S:
                st_size = val
            return S()
        return orig_stat(self)

    monkeypatch.setattr(pathlib.Path, 'stat', fake_stat)

    # Should return True because eventually sizes stabilize
    assert wait_for_stable_file(p, stable_seconds=0.0, timeout=5.0) is True
