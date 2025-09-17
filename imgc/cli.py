from pathlib import Path
from typing import Optional
import logging

from .compressor import Compressor
from .watcher import start_watch

logger = logging.getLogger(__name__)


def run_cli(args):
    compressor = Compressor(jpeg_quality=args.jpeg_quality, png_min=args.png_min, png_max=args.png_max, webp_quality=args.webp_quality, avif_quality=args.avif_quality)
    # Require explicit root; callers should provide it. If args.root is falsy, raise an error.
    if not getattr(args, 'root', None):
        raise ValueError('Root directory not provided to run_cli; pass --root or set IMGC_ROOT environment variable')

    start_watch(Path(args.root), compressor, workers=args.workers, file_timeout=args.file_timeout, stable_seconds=args.stable_seconds, new_delay=args.new_delay, compress_timeout=getattr(args, 'compress_timeout', None) or 0)
