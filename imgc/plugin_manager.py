"""
Plugin Manager for imgc - Handles discovery, loading, and management of file processors.

This module provides the core functionality for finding and loading user-defined
plugins from Python files, validating them, and managing their lifecycle.
"""

import importlib.util
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Type
import logging
import traceback
import ast
import os

from .plugin_api import (
    FileProcessor,
    ProcessorError,
    ProcessorValidationError,
    PluginArgument,
)

logger = logging.getLogger(__name__)


class PluginManager:
    """
    Manages the discovery, loading, and lifecycle of file processor plugins.

    The PluginManager scans specified directories for Python files containing
    FileProcessor implementations, loads them safely, and provides access to
    the loaded processors.
    """

    def __init__(self, plugin_dirs: Optional[List[Path]] = None):
        """
        Initialize the plugin manager.

        Args:
            plugin_dirs: List of directories to scan for plugins.
                        If None, uses default locations.
                        Built-in plugins are always included.
        """
        if plugin_dirs:
            # User provided custom directories - use them plus built-in plugins
            self.plugin_dirs = list(plugin_dirs)
            # Always include built-in plugins
            builtin_plugins = Path(__file__).parent / "plugins" / "builtin"
            if builtin_plugins not in self.plugin_dirs:
                self.plugin_dirs.append(builtin_plugins)
        else:
            # Use default plugin directories
            self.plugin_dirs = self._get_default_plugin_dirs()
        self.processors: List[FileProcessor] = []
        self.failed_plugins: Dict[str, str] = {}  # filename -> error message
        self.loaded_modules: Dict[str, Any] = {}  # filename -> module

    def _get_default_plugin_dirs(self) -> List[Path]:
        """Get default plugin directories."""
        dirs = []

        # Plugins directory next to the executable (or main.py in development)
        try:
            # Try to find the executable directory first
            if hasattr(sys, "frozen") and sys.frozen:
                # Running as PyInstaller executable
                executable_dir = Path(sys.executable).parent
            else:
                # Running from source - find main.py location
                main_module = sys.modules.get("__main__")
                if (
                    main_module
                    and hasattr(main_module, "__file__")
                    and main_module.__file__
                ):
                    executable_dir = Path(main_module.__file__).parent
                else:
                    # Fallback to current working directory
                    executable_dir = Path.cwd()

            local_plugins = executable_dir / "plugins"
            dirs.append(local_plugins)

        except Exception:
            # Fallback to current directory if anything goes wrong
            dirs.append(Path.cwd() / "plugins")

        # Built-in plugins directory
        builtin_plugins = Path(__file__).parent / "plugins" / "builtin"
        dirs.append(builtin_plugins)

        return dirs

    def discover_plugins(self) -> None:
        """
        Discover and load all plugins from configured directories.

        This method scans all plugin directories for Python files,
        validates them, and loads any valid FileProcessor implementations.
        """
        logger.info("Discovering plugins...")
        self.processors.clear()
        self.failed_plugins.clear()
        self.loaded_modules.clear()

        for plugin_dir in self.plugin_dirs:
            if not plugin_dir.exists():
                logger.debug(f"Plugin directory does not exist: {plugin_dir}")
                continue

            logger.debug(f"Scanning plugin directory: {plugin_dir}")
            self._scan_directory(plugin_dir)

        # Sort processors by priority
        self.processors.sort(key=lambda p: p.priority)

        logger.info(
            f"Loaded {len(self.processors)} plugins, "
            f"{len(self.failed_plugins)} failed"
        )

        if self.failed_plugins:
            logger.warning("Failed plugins: %s", ", ".join(self.failed_plugins.keys()))

    def _scan_directory(self, plugin_dir: Path) -> None:
        """Scan a directory for plugin files."""
        try:
            for plugin_file in plugin_dir.glob("*.py"):
                if plugin_file.name.startswith("_"):
                    continue  # Skip private files

                try:
                    processors = self._load_plugin_file(plugin_file)
                    self.processors.extend(processors)
                    logger.debug(
                        f"Loaded {len(processors)} processors from {plugin_file.name}"
                    )
                except Exception as e:
                    error_msg = f"{type(e).__name__}: {e}"
                    self.failed_plugins[plugin_file.name] = error_msg
                    logger.warning(
                        f"Failed to load plugin {plugin_file.name}: {error_msg}"
                    )

        except Exception as e:
            logger.error(f"Error scanning plugin directory {plugin_dir}: {e}")

    def _load_plugin_file(self, plugin_file: Path) -> List[FileProcessor]:
        """
        Load processors from a single plugin file.

        Args:
            plugin_file: Path to the plugin file

        Returns:
            List of loaded FileProcessor instances

        Raises:
            ProcessorValidationError: If the plugin file is invalid
            Exception: For other loading errors
        """
        # First, validate the Python syntax
        self._validate_plugin_syntax(plugin_file)

        # Load the module
        module_name = f"imgc_plugin_{plugin_file.stem}"
        spec = importlib.util.spec_from_file_location(module_name, plugin_file)

        if spec is None or spec.loader is None:
            raise ProcessorValidationError(
                f"Could not create module spec for {plugin_file}"
            )

        module = importlib.util.module_from_spec(spec)

        # Store reference to prevent garbage collection
        self.loaded_modules[plugin_file.name] = module

        # Execute the module
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            raise ProcessorValidationError(f"Error executing plugin: {e}")

        # Find FileProcessor classes
        processors = []
        for attr_name in dir(module):
            attr = getattr(module, attr_name)

            if (
                isinstance(attr, type)
                and issubclass(attr, FileProcessor)
                and attr is not FileProcessor
            ):

                try:
                    # Instantiate the processor
                    processor = attr()
                    self._validate_processor(processor, plugin_file)
                    processors.append(processor)
                    logger.debug(f"Loaded processor: {processor.name}")

                except Exception as e:
                    logger.warning(
                        f"Failed to instantiate processor {attr_name} "
                        f"from {plugin_file.name}: {e}"
                    )

        if not processors:
            raise ProcessorValidationError("No valid FileProcessor classes found")

        return processors

    def _validate_plugin_syntax(self, plugin_file: Path) -> None:
        """Validate that the plugin file has valid Python syntax."""
        try:
            with open(plugin_file, "r", encoding="utf-8") as f:
                source = f.read()
            ast.parse(source, filename=str(plugin_file))
        except SyntaxError as e:
            raise ProcessorValidationError(f"Syntax error: {e}")
        except Exception as e:
            raise ProcessorValidationError(f"Could not read plugin file: {e}")

    def _validate_processor(self, processor: FileProcessor, plugin_file: Path) -> None:
        """Validate that a processor implements the required interface correctly."""
        try:
            # Test required properties
            name = processor.name
            if not isinstance(name, str) or not name.strip():
                raise ProcessorValidationError(
                    "Processor name must be a non-empty string"
                )

            extensions = processor.supported_extensions
            if not isinstance(extensions, list) or not extensions:
                raise ProcessorValidationError(
                    "supported_extensions must be a non-empty list"
                )

            for ext in extensions:
                if not isinstance(ext, str) or not ext.startswith("."):
                    raise ProcessorValidationError(
                        f"Invalid extension: {ext} (must start with '.')"
                    )

            # Test optional properties
            priority = processor.priority
            if not isinstance(priority, int):
                raise ProcessorValidationError("priority must be an integer")

            # Test that process method exists and is callable
            if not hasattr(processor, "process") or not callable(processor.process):
                raise ProcessorValidationError(
                    "process method is required and must be callable"
                )

        except Exception as e:
            if isinstance(e, ProcessorValidationError):
                raise
            raise ProcessorValidationError(f"Validation error: {e}")

    def get_processors_for_file(self, file_path: Path) -> List[FileProcessor]:
        """
        Get all processors that can handle the given file.

        Args:
            file_path: Path to the file

        Returns:
            List of processors that can handle the file, sorted by priority
        """
        applicable = []
        for processor in self.processors:
            try:
                if processor.can_process(file_path):
                    applicable.append(processor)
            except Exception as e:
                logger.warning(
                    f"Error checking if {processor.name} can process "
                    f"{file_path}: {e}"
                )

        # Sort by priority (lower numbers first)
        applicable.sort(key=lambda p: p.priority)
        return applicable

    def get_processor_by_name(self, name: str) -> Optional[FileProcessor]:
        """Get a processor by its name."""
        for processor in self.processors:
            if processor.name == name:
                return processor
        return None

    def get_all_processors(self) -> List[FileProcessor]:
        """Get all loaded processors."""
        return self.processors.copy()

    def get_supported_extensions(self) -> List[str]:
        """Get all file extensions supported by loaded processors."""
        extensions = set()
        for processor in self.processors:
            extensions.update(ext.lower() for ext in processor.supported_extensions)
        return sorted(extensions)

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about loaded plugins."""
        return {
            "total_processors": len(self.processors),
            "failed_plugins": len(self.failed_plugins),
            "supported_extensions": len(self.get_supported_extensions()),
            "plugin_directories": [str(d) for d in self.plugin_dirs],
            "processors": [p.get_info() for p in self.processors],
            "failed": dict(self.failed_plugins),
        }

    def reload_plugins(self) -> None:
        """Reload all plugins from disk."""
        logger.info("Reloading plugins...")

        # Clear loaded modules from sys.modules to force reload
        for module_name, module in self.loaded_modules.items():
            if hasattr(module, "__name__") and module.__name__ in sys.modules:
                del sys.modules[module.__name__]

        self.discover_plugins()

    def create_plugin_directories(self) -> None:
        """Create plugin directories if they don't exist."""
        for plugin_dir in self.plugin_dirs:
            try:
                plugin_dir.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Created plugin directory: {plugin_dir}")
            except Exception as e:
                logger.warning(f"Could not create plugin directory {plugin_dir}: {e}")

    def get_all_plugin_arguments(self) -> Dict[str, List[PluginArgument]]:
        """
        Collect all arguments from all loaded plugins.

        Returns:
            Dict mapping plugin namespace to list of arguments
        """
        all_args = {}
        for processor in self.processors:
            try:
                namespace = processor.get_plugin_namespace()
                plugin_args = processor.get_plugin_arguments()
                if plugin_args:
                    all_args[namespace] = plugin_args
                    logger.debug(
                        f"Collected {len(plugin_args)} arguments from {processor.name}"
                    )
            except Exception as e:
                logger.warning(f"Error collecting arguments from {processor.name}: {e}")

        return all_args

    def configure_plugins_from_args(self, args) -> None:
        """
        Configure all loaded plugins from parsed command-line arguments.

        Args:
            args: Parsed argparse.Namespace containing plugin arguments
        """
        for processor in self.processors:
            try:
                processor.configure_from_args(args)
            except Exception as e:
                logger.warning(f"Error configuring {processor.name}: {e}")
