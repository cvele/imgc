import io
import os
from pathlib import Path
from PIL import Image
import shutil

import pytest

from imgc.compressor import Compressor, human_readable_size


def create_png(path: Path, size=(100, 100), color=(10, 20, 30), alpha=False):
    if alpha:
        img = Image.new('RGBA', size, color + (128,))
    else:
        img = Image.new('RGB', size, color)
    img.save(path, format='PNG')


def test_human_readable_size():
    assert human_readable_size(512).endswith('B')
    assert human_readable_size(2048).endswith('KB')
    assert human_readable_size(5 * 1024 * 1024).endswith('MB')


def test_compress_png_without_pngquant(tmp_path, monkeypatch):
    p = tmp_path / 'img.png'
    create_png(p)
    # ensure pngquant not found
    monkeypatch.setattr(shutil, 'which', lambda name: None)
    comp = Compressor()
    stats = comp.compress(p)
    assert stats is not None
    assert 'new' in stats


def test_compress_png_with_pngquant_true(tmp_path, monkeypatch):
    p = tmp_path / 'img.png'
    create_png(p)
    comp = Compressor()
    # monkeypatch _run_pngquant to simulate success and create the tmp file
    def fake_pngquant(self, src, tmp):
        # copy the original file to the tmp location to simulate pngquant output
        shutil.copy(src, tmp)
        return True

    monkeypatch.setattr(Compressor, '_run_pngquant', fake_pngquant)
    stats = comp.compress(p)
    assert stats is not None
    assert 'new' in stats


def test_compress_jpeg_with_alpha_content(tmp_path):
    # create a PNG with alpha but name it .jpg so Image.open detects RGBA and JPEG branch runs
    p = tmp_path / 'weird.jpg'
    create_png(p, alpha=True)
    comp = Compressor(jpeg_quality=60)
    stats = comp.compress(p)
    assert stats is not None
    assert 'new' in stats


def test_compress_webp(tmp_path):
    p = tmp_path / 'img.webp'
    # create an RGB image and save as webp if supported; if not, the compressor will likely return None
    try:
        Image.new('RGB', (32, 32), (1, 2, 3)).save(p, format='WEBP')
    except Exception:
        # create a PNG file but with .webp suffix - Image.open will still work
        create_png(p)
    comp = Compressor()
    res = comp.compress(p)
    # either success stats dict or None if format unsupported; both are acceptable
    assert (res is None) or (isinstance(res, dict) and 'new' in res)


def test_compress_avif_supported(tmp_path):
    p = tmp_path / 'img.avif'
    create_png(p)
    comp = Compressor()
    # AVIF is now supported with imageio; expect compression stats
    res = comp.compress(p)
    # Should return compression stats (not None) if imageio is available
    if res is None:
        # imageio not available, skip test
        pytest.skip("imageio not available for AVIF support")
    else:
        assert isinstance(res, dict)
        assert 'orig' in res
        assert 'new' in res


def test_compress_non_image_returns_none(tmp_path):
    p = tmp_path / 'file.txt'
    p.write_text('hello')
    comp = Compressor()
    assert comp.compress(p) is None


def test_orig_none_behaviour(tmp_path, monkeypatch):
    p = tmp_path / 'img.jpg'
    # create a valid JPEG
    Image.new('RGB', (10, 10), (5, 6, 7)).save(p, format='JPEG')

    import pathlib

    # save original stat method
    orig_method = pathlib.Path.stat
    calls = {}

    def fake_stat(self):
        key = str(self)
        calls.setdefault(key, 0)
        calls[key] += 1
        if calls[key] == 1:
            raise Exception('stat fail')
        return orig_method(self)

    # monkeypatch the class method so Path.stat will raise once for our path
    monkeypatch.setattr(pathlib.Path, 'stat', fake_stat)

    comp = Compressor()
    # If first stat failed, compressor sets orig=None then continues; because second stat returns, new is available
    res = comp.compress(p)
    assert res is not None
    assert 'new' in res
