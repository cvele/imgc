#!/usr/bin/env python3
"""Command-line entrypoint for the universal file processor.

Uses the plugin system to handle any file type through user-defined plugins.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

from imgc.plugin_watcher import PluginWatcher
from imgc.plugin_manager import PluginManager
from imgc import config
from imgc.logging_config import configure_logging

logging.basicConfig(level=logging.INFO, format="[imgc] %(message)s")
logger = logging.getLogger(__name__)

# Environment variable parsing constants
ENV_TRUE_VALUES = {"true", "1", "yes", "on"}


def _env_str(name, default=None):
    """Get string environment variable."""
    return os.environ.get(name, default)


def _env_int(name, default=None):
    """Get integer environment variable with error handling."""
    v = os.environ.get(name)
    return int(v) if v is not None and v != "" else default


def _env_float(name, default=None):
    """Get float environment variable with error handling."""
    v = os.environ.get(name)
    return float(v) if v is not None and v != "" else default


def _env_bool(name, default=False):
    """Get boolean environment variable with multiple accepted formats.

    Accepted true values: 'true', '1', 'yes', 'on' (case-insensitive)
    All other values are considered false.
    """
    value = _env_str(name, default)
    if value == default:
        return default
    return str(value).lower() in ENV_TRUE_VALUES


def add_plugin_arguments_to_parser(
    parser: argparse.ArgumentParser, plugin_manager: PluginManager
) -> None:
    """
    Add plugin-specific arguments to the argument parser.

    Args:
        parser: The argparse parser to add arguments to
        plugin_manager: Plugin manager containing loaded plugins
    """
    all_plugin_args = plugin_manager.get_all_plugin_arguments()

    if not all_plugin_args:
        return

    # Create a plugin arguments group for better help organization
    plugin_group = parser.add_argument_group("Plugin Arguments")

    for namespace, plugin_args in all_plugin_args.items():
        for plugin_arg in plugin_args:
            # Build argument name with namespace prefix (convert underscores to hyphens for CLI)
            cli_arg_name = plugin_arg.name.replace("_", "-")
            arg_name = f"--{namespace}-{cli_arg_name}"
            dest_name = f"{namespace}_{plugin_arg.name}".replace("-", "_")

            # Get environment variable default if available
            # Find the processor that owns this argument
            processor = None
            for proc in plugin_manager.processors:
                if proc.get_plugin_namespace() == namespace:
                    processor = proc
                    break

            if processor:
                env_default = processor._get_env_value(plugin_arg, namespace)
                if env_default is not None:
                    default_value = env_default
                else:
                    default_value = plugin_arg.default
            else:
                default_value = plugin_arg.default

            # Build argument kwargs
            arg_kwargs = {
                "dest": dest_name,
                "default": default_value,
                "help": plugin_arg.help,
            }

            # Handle different argument types
            if plugin_arg.type == bool:
                if default_value:
                    # If default is True, create --no-xxx argument
                    arg_kwargs["action"] = "store_false"
                    arg_name = f"--no-{namespace}-{plugin_arg.name}"
                else:
                    # If default is False, create --xxx argument
                    arg_kwargs["action"] = "store_true"
            else:
                arg_kwargs["type"] = plugin_arg.type
                if plugin_arg.choices:
                    arg_kwargs["choices"] = plugin_arg.choices
                if plugin_arg.required:
                    arg_kwargs["required"] = True

            # Add the argument to the parser
            plugin_group.add_argument(arg_name, **arg_kwargs)
            logger.debug(f"Added plugin argument: {arg_name}")

def create_plugin_manager_for_args(
    plugin_dirs: Optional[List[Path]] = None,
) -> PluginManager:
    """
    Create and initialize a plugin manager for argument discovery.

    This is used in the first phase to discover plugin arguments before
    creating the main plugin manager.

    Args:
        plugin_dirs: Optional list of plugin directories

    Returns:
        PluginManager: Initialized plugin manager with discovered plugins
    """
    temp_manager = PluginManager(plugin_dirs)
    temp_manager.create_plugin_directories()
    temp_manager.discover_plugins()
    return temp_manager


def main():
    # Allow environment variables to provide defaults (executor-friendly).
    # Naming: IMGC_<OPTION_NAME>, e.g. IMGC_ROOT, IMGC_STABLE_SECONDS

    env_root = _env_str("IMGC_ROOT", None)
    env_stable = _env_float("IMGC_STABLE_SECONDS", config.DEFAULT_STABLE_SECONDS)
    env_new_delay = _env_float("IMGC_NEW_DELAY", config.DEFAULT_NEW_DELAY)
    env_workers = _env_int("IMGC_WORKERS", config.DEFAULT_WORKERS)
    env_compress_timeout = _env_float(
        "IMGC_COMPRESS_TIMEOUT", config.DEFAULT_COMPRESS_TIMEOUT
    )
    env_log_file = _env_str(
        "IMGC_LOG_FILE", str(Path(config.DEFAULT_LOG_DIR) / config.DEFAULT_LOG_FILENAME)
    )
    env_log_level = _env_str("IMGC_LOG_LEVEL", config.DEFAULT_LOG_LEVEL)
    env_process_existing = _env_bool(
        "IMGC_PROCESS_EXISTING", config.DEFAULT_PROCESS_EXISTING
    )

    # Phase 1: Create basic parser with core arguments
    parser = argparse.ArgumentParser(
        description="Universal file processor with plugin system"
    )
    # Make --root optional at argparse level but enforce presence below so we can give a clear error
    # when neither IMGC_ROOT nor --root is provided.
    parser.add_argument(
        "--root",
        "-r",
        type=str,
        default=env_root,
        help="Root directory to watch (required unless IMGC_ROOT is set)",
    )
    parser.add_argument(
        "--stable-seconds",
        type=float,
        default=env_stable,
        help="Time to wait for file stability before processing",
    )
    parser.add_argument(
        "--new-delay",
        type=float,
        default=env_new_delay,
        help="Delay (seconds) before processing newly created files",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=env_workers,
        help="Number of worker threads to use when processing existing files",
    )
    parser.add_argument(
        "--compress-timeout",
        type=float,
        default=env_compress_timeout,
        help="Per-processor timeout in seconds; 0 = no timeout",
    )
    parser.add_argument(
        "--process-existing",
        action="store_true",
        default=env_process_existing,
        help="Process existing files on startup (default: watch-only mode)",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=env_log_file,
        help="Path to log file (optional). Can be set via IMGC_LOG_FILE env var",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default=env_log_level,
        choices=["debug", "info", "warning", "quiet"],
        help="Logging level (or set IMGC_LOG_LEVEL env var)",
    )
    parser.add_argument(
        "--plugin-dirs",
        type=str,
        nargs="*",
        help="Directories to scan for plugins (default: ./plugins and built-in plugins)",
    )

    # Phase 2: Discover plugins and add their arguments
    # Convert plugin directories to Path objects for discovery
    plugin_dirs = None
    if "--plugin-dirs" in sys.argv:
        # Parse plugin-dirs early to discover plugins
        temp_args, _ = parser.parse_known_args()
        if temp_args.plugin_dirs:
            plugin_dirs = [Path(d).resolve() for d in temp_args.plugin_dirs]

    # Create temporary plugin manager to discover plugin arguments
    temp_plugin_manager = create_plugin_manager_for_args(plugin_dirs)

    # Add plugin arguments to parser
    add_plugin_arguments_to_parser(parser, temp_plugin_manager)

    # Phase 3: Parse all arguments (core + plugin)
    args = parser.parse_args()

    # Configure logging early
    configure_logging(args.log_file, args.log_level)

    # Enforce explicit root: if not provided via CLI or IMGC_ROOT, fail fast with a helpful message.
    if not args.root:
        parser.error(
            "Root directory not provided. Set --root or IMGC_ROOT environment variable to the directory to watch."
        )

    # Normalize the path to handle Windows trailing backslashes and other path issues
    root_path = Path(args.root).resolve()

    # Validate that the directory exists
    if not root_path.exists():
        parser.error(f"Root directory does not exist: {root_path}")
    if not root_path.is_dir():
        parser.error(f"Root path is not a directory: {root_path}")

    # Convert plugin directories to Path objects
    plugin_dirs = None
    if args.plugin_dirs:
        plugin_dirs = [Path(d).resolve() for d in args.plugin_dirs]

    # Create and start the plugin-based watcher (reuse the temp plugin manager to avoid double loading)
    logger.info(f"Starting universal file processor on: {root_path}")

    watcher = PluginWatcher(
        root_path=root_path,
        plugin_manager=temp_plugin_manager,  # Reuse the plugin manager
        stable_seconds=args.stable_seconds,
        new_delay=args.new_delay,
        compress_timeout=args.compress_timeout,
        max_concurrent=1,  # Conservative default
    )

    # Configure plugins with the parsed arguments
    watcher.plugin_manager.configure_plugins_from_args(args)

    # Start watching with existing file processing option
    watcher.start_watching(process_existing=args.process_existing, workers=args.workers)


if __name__ == "__main__":
    main()
