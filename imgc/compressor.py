from pathlib import Path
from typing import Optional
import logging
import shutil
import subprocess

from PIL import Image

logger = logging.getLogger(__name__)


def human_readable_size(n: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if n < 1024.0:
            return f"{n:.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}PB"


class Compressor:
    def __init__(self, jpeg_quality: int = 78, png_min: int = 0, png_max: int = 95, webp_quality: int = 72, avif_quality: int = 45):
        self.jpeg_quality = jpeg_quality
        self.png_min = png_min
        self.png_max = png_max
        self.webp_quality = webp_quality
        self.avif_quality = avif_quality

    def _run_pngquant(self, src: Path, tmp: Path) -> bool:
        pngquant = shutil.which('pngquant')
        if not pngquant:
            return False
        cmd = [pngquant, '--quality', f'{self.png_min}-{self.png_max}', '--output', str(tmp), '--force', str(src)]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True
        except subprocess.CalledProcessError:
            return False

    def compress(self, path: Path, tmp_suffix: str = '.imgc.tmp') -> Optional[dict]:
        """Compress a file in-place. Returns a dict with stats or None on failure."""
        try:
            orig = path.stat().st_size
        except Exception:
            orig = None
        tmp = path.with_suffix(path.suffix + tmp_suffix)
        try:
            if path.suffix.lower() in ('.jpg', '.jpeg'):
                img = Image.open(path)
                if img.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1])
                    img = background
                img.save(tmp, format='JPEG', quality=self.jpeg_quality, optimize=True)
                tmp.replace(path)
            elif path.suffix.lower() == '.png':
                if self._run_pngquant(path, tmp):
                    tmp.replace(path)
                else:
                    img = Image.open(path)
                    img.save(tmp, format='PNG', optimize=True)
                    tmp.replace(path)
            elif path.suffix.lower() == '.webp':
                img = Image.open(path)
                img.save(tmp, format='WEBP', quality=self.webp_quality)
                tmp.replace(path)
            elif path.suffix.lower() == '.avif':
                try:
                    import imageio.v3 as iio
                    img = Image.open(path)
                    arr = img.convert('RGB')
                    # Note: AVIF quality parameter not supported in current imageio version
                    # Uses default compression settings
                    iio.imwrite(str(tmp), arr, extension='.avif')
                    tmp.replace(path)
                except ImportError:
                    logger.warning('imageio not installed; AVIF compression skipped')
                    return None
                except Exception as e:
                    logger.warning('AVIF write failed: %s', e)
                    return None
            else:
                return None

            new = path.stat().st_size
            stats = {}
            if orig and orig > 0:
                saved = orig - new
                percent = (saved / orig) * 100
                stats = {
                    'orig': orig,
                    'new': new,
                    'saved': saved,
                    'percent': percent,
                }
            else:
                stats = {'new': new}
            return stats
        except Exception:
            logger.exception('Failed to compress %s', path)
            try:
                if tmp.exists():
                    tmp.unlink()
            except Exception:
                pass
            return None
