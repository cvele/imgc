"""Logging setup helper for imgc.

Provides a `configure_logging(log_file: str|None, level: str)` helper that sets
up console and file logging. Supports levels: 'debug', 'info', 'warning', 'quiet'.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


def _level_from_name(name: str) -> int:
    name = (name or "").lower()
    if name == "debug":
        return logging.DEBUG
    if name == "warning":
        return logging.WARNING
    if name == "quiet":
        # quiet means minimal console noise; map to ERROR but allow file
        return logging.ERROR
    return logging.INFO


def configure_logging(log_file: Optional[str], level: str = "info") -> None:
    # Determine numeric level
    lvl = _level_from_name(level)

    root = logging.getLogger()
    # If handlers already configured, remove them and reconfigure
    for h in list(root.handlers):
        root.removeHandler(h)

    # Console handler: unless quiet (ERROR still prints errors)
    ch = logging.StreamHandler()
    ch.setLevel(lvl)
    ch.setFormatter(logging.Formatter("[imgc] %(message)s"))
    root.addHandler(ch)

    # File handler (rotating) if requested
    if log_file:
        p = Path(log_file)
        p.parent.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(
            str(p), maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        fh.setLevel(logging.DEBUG)  # capture debug in file regardless of console level
        fh.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        root.addHandler(fh)

    root.setLevel(logging.DEBUG if lvl == logging.DEBUG else logging.INFO)
