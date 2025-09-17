#!/usr/bin/env python3
"""Command-line entrypoint for the image watcher.

Kept minimal: delegates implementation to the `imgc` package.
"""
from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from imgc.compressor import Compressor
from imgc.watcher import start_watch
from imgc import config
from imgc.logging_config import configure_logging

logging.basicConfig(level=logging.INFO, format='[imgc] %(message)s')
logger = logging.getLogger(__name__)


def main():
    # Allow environment variables to provide defaults (executor-friendly).
    # Naming: IMGC_<OPTION_NAME>, e.g. IMGC_ROOT, IMGC_JPEG_QUALITY
    env = os.environ
    def _env_str(name, default=None):
        return env.get(name, default)
    def _env_int(name, default=None):
        v = env.get(name)
        return int(v) if v is not None and v != '' else default
    def _env_float(name, default=None):
        v = env.get(name)
        return float(v) if v is not None and v != '' else default

    env_root = _env_str('IMGC_ROOT', None)
    env_jpeg = _env_int('IMGC_JPEG_QUALITY', config.DEFAULT_JPEG_QUALITY)
    env_png_min = _env_int('IMGC_PNG_MIN', config.DEFAULT_PNG_MIN)
    env_png_max = _env_int('IMGC_PNG_MAX', config.DEFAULT_PNG_MAX)
    env_webp = _env_int('IMGC_WEBP_QUALITY', config.DEFAULT_WEBP_QUALITY)
    env_avif = _env_int('IMGC_AVIF_QUALITY', config.DEFAULT_AVIF_QUALITY)
    env_stable = _env_float('IMGC_STABLE_SECONDS', config.DEFAULT_STABLE_SECONDS)
    env_new_delay = _env_float('IMGC_NEW_DELAY', config.DEFAULT_NEW_DELAY)
    env_workers = _env_int('IMGC_WORKERS', config.DEFAULT_WORKERS)
    env_file_timeout = _env_float('IMGC_FILE_TIMEOUT', config.DEFAULT_FILE_TIMEOUT)
    env_compress_timeout = _env_float('IMGC_COMPRESS_TIMEOUT', config.DEFAULT_COMPRESS_TIMEOUT)
    env_log_file = _env_str('IMGC_LOG_FILE', str(Path(config.DEFAULT_LOG_DIR) / config.DEFAULT_LOG_FILENAME))
    env_log_level = _env_str('IMGC_LOG_LEVEL', config.DEFAULT_LOG_LEVEL)
    env_process_existing = _env_str('IMGC_PROCESS_EXISTING', 'false').lower() in ('true', '1', 'yes', 'on')

    parser = argparse.ArgumentParser(description='Image auto-compress watcher (delegates to imgc package)')
    # Make --root optional at argparse level but enforce presence below so we can give a clear error
    # when neither IMGC_ROOT nor --root is provided.
    parser.add_argument('--root', '-r', type=str, default=env_root, help='Root directory to watch (required unless IMGC_ROOT is set)')
    parser.add_argument('--jpeg-quality', type=int, default=env_jpeg)
    parser.add_argument('--png-min', type=int, default=env_png_min)
    parser.add_argument('--png-max', type=int, default=env_png_max)
    parser.add_argument('--webp-quality', type=int, default=env_webp)
    parser.add_argument('--avif-quality', type=int, default=env_avif)
    parser.add_argument('--stable-seconds', type=float, default=env_stable)
    parser.add_argument('--new-delay', type=float, default=env_new_delay, help='Delay (seconds) before processing newly created files')
    parser.add_argument('--workers', type=int, default=env_workers, help='Number of worker threads to use when processing existing files')
    parser.add_argument('--file-timeout', type=float, default=env_file_timeout, help='Timeout (seconds) to wait for a file to stabilize during initial pass; 0 = no wait (fast)')
    parser.add_argument('--compress-timeout', type=float, default=env_compress_timeout, help='Per-file compression timeout in seconds; 0 = no timeout')
    parser.add_argument('--process-existing', action='store_true', default=env_process_existing, help='Process existing images on startup (default: watch-only mode)')
    parser.add_argument('--log-file', type=str, default=env_log_file, help='Path to log file (optional). Can be set via IMGC_LOG_FILE env var')
    parser.add_argument('--log-level', type=str, default=env_log_level, choices=['debug', 'info', 'warning', 'quiet'], help='Logging level (or set IMGC_LOG_LEVEL env var)')
    args = parser.parse_args()

    # Configure logging early
    configure_logging(args.log_file, args.log_level)

    # Enforce explicit root: if not provided via CLI or IMGC_ROOT, fail fast with a helpful message.
    if not args.root:
        parser.error('Root directory not provided. Set --root or IMGC_ROOT environment variable to the directory to watch.')

    # Normalize the path to handle Windows trailing backslashes and other path issues
    root_path = Path(args.root).resolve()
    
    # Validate that the directory exists
    if not root_path.exists():
        parser.error(f'Root directory does not exist: {root_path}')
    if not root_path.is_dir():
        parser.error(f'Root path is not a directory: {root_path}')

    compressor = Compressor(jpeg_quality=args.jpeg_quality, png_min=args.png_min, png_max=args.png_max, webp_quality=args.webp_quality, avif_quality=args.avif_quality)
    start_watch(root_path, compressor, workers=args.workers, file_timeout=args.file_timeout, stable_seconds=args.stable_seconds, new_delay=args.new_delay, compress_timeout=args.compress_timeout, scan_existing=args.process_existing)


if __name__ == '__main__':
    main()
