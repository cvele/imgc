"""Centralized default configuration for imgc.

Modify these values to change runtime defaults for the watcher and compressor.
"""

from pathlib import Path

# Compression quality defaults
DEFAULT_JPEG_QUALITY = 70
DEFAULT_PNG_MIN = 0
DEFAULT_PNG_MAX = 90
DEFAULT_WEBP_QUALITY = 70
DEFAULT_AVIF_QUALITY = 40

# Watcher behavior
DEFAULT_STABLE_SECONDS = 2.0
DEFAULT_NEW_DELAY = 0.0
DEFAULT_WORKERS = 2
DEFAULT_FILE_TIMEOUT = 0.0  # initial-pass stability wait; 0 = no wait for fast pass
DEFAULT_COMPRESS_TIMEOUT = 30.0  # per-file compress timeout; 0 = disabled

# Logging defaults
# Default log directory: place logs next to the package (project root) under ./logs
# Use the package file location to compute project root reliably when installed or run from source.
DEFAULT_LOG_DIR = str(Path(__file__).resolve().parents[1] / "logs")
# Default log filename (rotated by date/size as needed)
DEFAULT_LOG_FILENAME = "imgc.log"
# Default log level: one of 'debug', 'info', 'warning', 'quiet'
DEFAULT_LOG_LEVEL = "info"

# Processing behavior
DEFAULT_PROCESS_EXISTING = False  # Whether to process existing files on startup
