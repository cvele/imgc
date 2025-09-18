"""
Plugin API for imgc - Base classes and interfaces for file processors.

This module defines the core plugin interface that all file processors must implement.
Plugins are simple Python files that users can write to extend imgc's functionality.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Optional, NamedTuple
import logging
import argparse
import os

logger = logging.getLogger(__name__)


class PluginArgument(NamedTuple):
    """Definition of a plugin command-line argument."""

    name: str  # Argument name (without dashes)
    type: type = str  # Argument type (str, int, float, bool)
    default: Any = None  # Default value
    help: str = ""  # Help text for the argument
    choices: Optional[List[str]] = None  # Valid choices for the argument
    required: bool = False  # Whether the argument is required
    env_var: Optional[str] = None  # Environment variable name (auto-generated if None)


class ProcessorResult:
    """Standard result object returned by processors."""

    def __init__(
        self,
        success: bool = True,
        message: str = "",
        stats: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        self.success = success
        self.message = message
        self.stats = stats or {}
        self.context = context or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            "success": self.success,
            "message": self.message,
            "stats": self.stats,
            "context": self.context,
        }


class FileProcessor(ABC):
    """
    Base class for all file processors.

    Users create plugins by inheriting from this class and implementing
    the required methods. Each plugin handles specific file types and
    can perform any processing operation.

    Example:
        class MyProcessor(FileProcessor):
            @property
            def name(self):
                return "Document Converter"

            @property
            def supported_extensions(self):
                return [".txt", ".md"]

            def process(self, file_path, context):
                # Your processing logic here
                return ProcessorResult(success=True, message="Processed!")
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Human-readable name of the processor.

        Returns:
            str: Plugin name (e.g., "Image Optimizer", "Video Compressor")
        """
        pass

    @property
    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """
        File extensions this processor can handle.

        Returns:
            List[str]: List of extensions including the dot (e.g., [".jpg", ".png"])
        """
        pass

    @property
    def priority(self) -> int:
        """
        Execution priority for this processor.

        Lower numbers execute first. Use this to control the order
        when multiple processors handle the same file type.

        Returns:
            int: Priority value (default: 100)
        """
        return 100

    @property
    def version(self) -> str:
        """
        Version of this processor.

        Returns:
            str: Version string (default: "1.0.0")
        """
        return "1.0.0"

    @property
    def description(self) -> str:
        """
        Brief description of what this processor does.

        Returns:
            str: Description text
        """
        return f"Processes {', '.join(self.supported_extensions)} files"

    def can_process(self, file_path: Path) -> bool:
        """
        Check if this processor can handle the given file.

        Default implementation checks file extension against supported_extensions.
        Override this method for more complex logic (e.g., checking file content).

        Args:
            file_path (Path): Path to the file to check

        Returns:
            bool: True if this processor can handle the file
        """
        return file_path.suffix.lower() in [
            ext.lower() for ext in self.supported_extensions
        ]

    @abstractmethod
    def process(self, file_path: Path, context: Dict[str, Any]) -> ProcessorResult:
        """
        Process the given file.

        This is the main method that performs the actual file processing.
        It should be safe to call multiple times and should not modify
        the original file unless that's the intended behavior.

        Args:
            file_path (Path): Path to the file to process
            context (Dict[str, Any]): Context from previous processors in the chain

        Returns:
            ProcessorResult: Result of the processing operation

        Raises:
            Exception: Any processing errors (will be caught by the plugin manager)
        """
        pass

    def validate_file(self, file_path: Path) -> bool:
        """
        Validate that the file exists and is accessible.

        Args:
            file_path (Path): Path to validate

        Returns:
            bool: True if file is valid and accessible
        """
        try:
            return (
                file_path.exists()
                and file_path.is_file()
                and file_path.stat().st_size > 0
            )
        except Exception as e:
            logger.debug(f"File validation failed for {file_path}: {e}")
            return False

    def get_info(self) -> Dict[str, Any]:
        """
        Get information about this processor.

        Returns:
            Dict[str, Any]: Processor metadata
        """
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "supported_extensions": self.supported_extensions,
            "priority": self.priority,
        }

    def __str__(self) -> str:
        return f"{self.name} v{self.version}"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.name} ({', '.join(self.supported_extensions)})>"

    # Plugin argument system methods

    def get_plugin_arguments(self) -> List[PluginArgument]:
        """
        Define command-line arguments for this plugin.

        Override this method to declare plugin-specific arguments.
        Arguments will be automatically prefixed with the plugin namespace.

        Example:
            return [
                PluginArgument("quality", int, 85, "JPEG compression quality (1-100)"),
                PluginArgument("optimize", bool, True, "Enable optimization")
            ]

        Returns:
            List[PluginArgument]: List of argument definitions
        """
        return []

    def get_plugin_namespace(self) -> str:
        """
        Get the namespace prefix for this plugin's arguments and environment variables.

        Default implementation converts the plugin name to a safe namespace.
        Override to provide a custom namespace.

        Example:
            Plugin name: "Image Compressor" -> namespace: "image-compressor"
            CLI args: --image-compressor-quality, --image-compressor-optimize
            Env vars: IMGC_IMAGE_COMPRESSOR_QUALITY, IMGC_IMAGE_COMPRESSOR_OPTIMIZE

        Returns:
            str: Namespace prefix (lowercase, hyphen-separated)
        """
        return self.name.lower().replace(" ", "-").replace("_", "-")

    def configure_from_args(self, args: argparse.Namespace) -> None:
        """
        Configure the plugin from parsed command-line arguments.

        This method is called after argument parsing to allow plugins to
        extract their configuration from the args namespace.

        Args:
            args: Parsed command-line arguments containing plugin values
        """
        namespace = self.get_plugin_namespace()
        plugin_args = self.get_plugin_arguments()

        for plugin_arg in plugin_args:
            # Build the full argument name with namespace
            full_arg_name = f"{namespace}_{plugin_arg.name}".replace("-", "_")

            # Get the value from args if it exists
            if hasattr(args, full_arg_name):
                value = getattr(args, full_arg_name)
                # Set the attribute on the plugin instance
                setattr(self, plugin_arg.name, value)
                logger.debug(f"Configured {self.name}.{plugin_arg.name} = {value}")

    def _get_env_value(self, plugin_arg: PluginArgument, namespace: str) -> Any:
        """
        Get environment variable value for a plugin argument.

        Args:
            plugin_arg: The plugin argument definition
            namespace: Plugin namespace

        Returns:
            Environment variable value or None if not set
        """
        # Use custom env var name if provided, otherwise generate one
        if plugin_arg.env_var:
            env_name = plugin_arg.env_var
        else:
            # Generate env var name: IMGC_NAMESPACE_ARGNAME
            env_name = (
                f"IMGC_{namespace.upper().replace('-', '_')}_{plugin_arg.name.upper()}"
            )

        env_value = os.environ.get(env_name)
        if env_value is None:
            return None

        # Convert environment variable to the correct type
        try:
            if plugin_arg.type == bool:
                return env_value.lower() in {"true", "1", "yes", "on"}
            elif plugin_arg.type == int:
                return int(env_value)
            elif plugin_arg.type == float:
                return float(env_value)
            else:
                return env_value
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid environment variable {env_name}={env_value}: {e}")
            return None


class ProcessorError(Exception):
    """Exception raised by processors during file processing."""

    def __init__(
        self, message: str, processor_name: str = "", file_path: Optional[Path] = None
    ):
        self.message = message
        self.processor_name = processor_name
        self.file_path = file_path
        super().__init__(self.message)

    def __str__(self) -> str:
        parts = []
        if self.processor_name:
            parts.append(f"[{self.processor_name}]")
        if self.file_path:
            parts.append(f"({self.file_path})")
        parts.append(self.message)
        return " ".join(parts)


class ProcessorTimeout(ProcessorError):
    """Exception raised when a processor exceeds its timeout."""

    pass


class ProcessorValidationError(ProcessorError):
    """Exception raised when a processor fails validation."""

    pass
