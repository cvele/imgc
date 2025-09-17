import tempfile
from pathlib import Path
from PIL import Image

from imgc.compressor import Compressor


def create_sample_jpeg(path: Path, size=(800,600), color=(200,100,50)):
    img = Image.new('RGB', size, color)
    img.save(path, format='JPEG', quality=95)


def test_compress_jpeg(tmp_path):
    p = tmp_path / 'test.jpg'
    create_sample_jpeg(p)
    comp = Compressor(jpeg_quality=70)
    stats = comp.compress(p)
    assert stats is not None
    assert 'new' in stats
    assert stats['new'] < stats['orig']
