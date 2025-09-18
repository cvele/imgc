"""
Tests for the plugin API base classes and interfaces.

Tests the core plugin system components that all plugins build upon.
"""

import pytest
from pathlib import Path
from imgc.plugin_api import (
    FileProcessor,
    ProcessorResult,
    ProcessorError,
    ProcessorTimeout,
)


class TestProcessorResult:
    """Test the ProcessorResult class."""

    def test_basic_creation(self):
        """Test basic ProcessorResult creation."""
        result = ProcessorResult(success=True, message="Test successful")

        assert result.success is True
        assert result.message == "Test successful"
        assert result.stats == {}
        assert result.context == {}

    def test_full_creation(self):
        """Test ProcessorResult with all parameters."""
        stats = {"size": 1024, "compressed": True}
        context = {"format": "jpeg", "quality": 85}

        result = ProcessorResult(
            success=True, message="Compression complete", stats=stats, context=context
        )

        assert result.success is True
        assert result.message == "Compression complete"
        assert result.stats == stats
        assert result.context == context

    def test_to_dict(self):
        """Test ProcessorResult serialization."""
        result = ProcessorResult(
            success=False,
            message="Failed to process",
            stats={"error_count": 1},
            context={"retry": True},
        )

        expected = {
            "success": False,
            "message": "Failed to process",
            "stats": {"error_count": 1},
            "context": {"retry": True},
        }

        assert result.to_dict() == expected


class TestFileProcessor:
    """Test the FileProcessor base class."""

    def test_abstract_methods(self):
        """Test that FileProcessor cannot be instantiated directly."""
        with pytest.raises(TypeError):
            FileProcessor()

    def test_concrete_implementation(self):
        """Test a concrete FileProcessor implementation."""

        class TestProcessor(FileProcessor):
            @property
            def name(self):
                return "Test Processor"

            @property
            def supported_extensions(self):
                return [".txt", ".md"]

            def process(self, file_path, context):
                return ProcessorResult(
                    success=True,
                    message=f"Processed {file_path.name}",
                    stats={
                        "file_size": (
                            file_path.stat().st_size if file_path.exists() else 0
                        )
                    },
                )

        processor = TestProcessor()

        # Test properties
        assert processor.name == "Test Processor"
        assert processor.supported_extensions == [".txt", ".md"]
        assert processor.priority == 100  # Default
        assert processor.version == "1.0.0"  # Default
        assert ".txt" in processor.description and ".md" in processor.description

        # Test string representations
        assert "Test Processor v1.0.0" in str(processor)
        assert "TestProcessor" in repr(processor)
        assert ".txt" in repr(processor)

    def test_can_process_default(self):
        """Test default can_process implementation."""

        class TestProcessor(FileProcessor):
            @property
            def name(self):
                return "Test Processor"

            @property
            def supported_extensions(self):
                return [".txt", ".md"]

            def process(self, file_path, context):
                return ProcessorResult(success=True, message="OK")

        processor = TestProcessor()

        # Test extension matching
        assert processor.can_process(Path("test.txt"))
        assert processor.can_process(Path("README.md"))
        assert processor.can_process(Path("file.TXT"))  # Case insensitive
        assert not processor.can_process(Path("image.jpg"))
        assert not processor.can_process(Path("script.py"))

    def test_can_process_override(self):
        """Test overriding can_process with custom logic."""

        class SizeBasedProcessor(FileProcessor):
            @property
            def name(self):
                return "Size Based Processor"

            @property
            def supported_extensions(self):
                return [".txt"]

            def can_process(self, file_path):
                # Only process .txt files smaller than 1KB
                if not super().can_process(file_path):
                    return False
                try:
                    return file_path.stat().st_size < 1024
                except:
                    return False

            def process(self, file_path, context):
                return ProcessorResult(success=True, message="OK")

        processor = SizeBasedProcessor()

        # This would require actual files to test fully
        # For now, just test that the method can be overridden
        assert hasattr(processor, "can_process")
        assert callable(processor.can_process)

    def test_validate_file(self):
        """Test file validation method."""

        class TestProcessor(FileProcessor):
            @property
            def name(self):
                return "Test Processor"

            @property
            def supported_extensions(self):
                return [".txt"]

            def process(self, file_path, context):
                return ProcessorResult(success=True, message="OK")

        processor = TestProcessor()

        # Test with non-existent file
        assert not processor.validate_file(Path("/non/existent/file.txt"))

        # Test with this test file (should exist and be valid)
        test_file = Path(__file__)
        assert processor.validate_file(test_file)

    def test_get_info(self):
        """Test processor info retrieval."""

        class TestProcessor(FileProcessor):
            @property
            def name(self):
                return "Advanced Test Processor"

            @property
            def supported_extensions(self):
                return [".txt", ".md", ".rst"]

            @property
            def version(self):
                return "2.1.0"

            @property
            def priority(self):
                return 50

            @property
            def description(self):
                return "A processor for testing purposes"

            def process(self, file_path, context):
                return ProcessorResult(success=True, message="OK")

        processor = TestProcessor()
        info = processor.get_info()

        expected = {
            "name": "Advanced Test Processor",
            "version": "2.1.0",
            "description": "A processor for testing purposes",
            "supported_extensions": [".txt", ".md", ".rst"],
            "priority": 50,
        }

        assert info == expected


class TestProcessorExceptions:
    """Test processor exception classes."""

    def test_processor_error(self):
        """Test ProcessorError exception."""
        error = ProcessorError(
            "Something went wrong", "TestProcessor", Path("/test/file.txt")
        )

        assert error.message == "Something went wrong"
        assert error.processor_name == "TestProcessor"
        assert error.file_path == Path("/test/file.txt")
        # Use cross-platform path comparison
        error_str = str(error)
        assert "[TestProcessor]" in error_str
        assert "Something went wrong" in error_str
        assert "file.txt" in error_str

    def test_processor_error_minimal(self):
        """Test ProcessorError with minimal information."""
        error = ProcessorError("Error occurred")

        assert error.message == "Error occurred"
        assert error.processor_name == ""
        assert error.file_path is None
        assert str(error) == "Error occurred"

    def test_processor_timeout(self):
        """Test ProcessorTimeout exception."""
        timeout = ProcessorTimeout(
            "Operation timed out", "SlowProcessor", Path("/big/file.dat")
        )

        assert isinstance(timeout, ProcessorError)
        assert timeout.message == "Operation timed out"
        assert timeout.processor_name == "SlowProcessor"
        assert timeout.file_path == Path("/big/file.dat")

    def test_processor_validation_error(self):
        """Test ProcessorValidationError exception."""
        from imgc.plugin_api import ProcessorValidationError

        validation_error = ProcessorValidationError(
            "Invalid plugin format", "BadPlugin"
        )

        assert isinstance(validation_error, ProcessorError)
        assert validation_error.message == "Invalid plugin format"
        assert validation_error.processor_name == "BadPlugin"


class TestProcessorIntegration:
    """Integration tests for processor components."""

    def test_processor_with_temp_file(self, tmp_path):
        """Test processor with actual temporary files."""

        class FileStatsProcessor(FileProcessor):
            @property
            def name(self):
                return "File Stats Processor"

            @property
            def supported_extensions(self):
                return [".txt", ".log"]

            def process(self, file_path, context):
                if not self.validate_file(file_path):
                    return ProcessorResult(
                        success=False, message=f"Invalid file: {file_path}"
                    )

                # Read file and analyze
                content = file_path.read_text()
                lines = content.split("\n")
                words = content.split()

                stats = {
                    "file_size": file_path.stat().st_size,
                    "line_count": len(lines),
                    "word_count": len(words),
                    "char_count": len(content),
                }

                return ProcessorResult(
                    success=True,
                    message=f"Analyzed {file_path.name}: {len(words)} words, {len(lines)} lines",
                    stats=stats,
                    context={"analyzed": True, "type": "text"},
                )

        processor = FileStatsProcessor()

        # Create test file
        test_file = tmp_path / "test.txt"
        test_content = "Hello world!\nThis is a test file.\nIt has multiple lines."
        test_file.write_text(test_content)

        # Test processing
        assert processor.can_process(test_file)
        result = processor.process(test_file, {})

        assert result.success
        assert "test.txt" in result.message
        assert result.stats["line_count"] == 3
        assert (
            result.stats["word_count"] == 11
        )  # "Hello world! This is a test file. It has multiple lines."
        # File size may differ on Windows due to CRLF line endings
        actual_file_size = test_file.stat().st_size
        assert result.stats["file_size"] == actual_file_size
        assert result.context["analyzed"] is True
        assert result.context["type"] == "text"


class TestPluginArgumentSystem:
    """Test the plugin argument declaration and configuration system."""

    def test_plugin_argument_creation(self):
        """Test creating PluginArgument instances."""
        from imgc.plugin_api import PluginArgument

        # Test basic argument
        arg = PluginArgument("quality", int, 85, "Quality setting")
        assert arg.name == "quality"
        assert arg.type == int
        assert arg.default == 85
        assert arg.help == "Quality setting"
        assert arg.choices is None
        assert arg.required is False
        assert arg.env_var is None

        # Test argument with all options
        arg_full = PluginArgument(
            "format",
            str,
            "auto",
            "Output format",
            choices=["auto", "jpg", "png"],
            required=True,
            env_var="CUSTOM_FORMAT",
        )
        assert arg_full.choices == ["auto", "jpg", "png"]
        assert arg_full.required is True
        assert arg_full.env_var == "CUSTOM_FORMAT"

    def test_default_plugin_arguments(self):
        """Test that default FileProcessor returns empty arguments."""
        from imgc.plugin_api import FileProcessor

        class TestProcessor(FileProcessor):
            @property
            def name(self):
                return "Test"

            @property
            def supported_extensions(self):
                return [".test"]

            def process(self, file_path, context):
                return ProcessorResult(success=True)

        processor = TestProcessor()
        args = processor.get_plugin_arguments()
        assert args == []

    def test_default_plugin_namespace(self):
        """Test default namespace generation."""
        from imgc.plugin_api import FileProcessor

        class TestProcessor(FileProcessor):
            @property
            def name(self):
                return "My Test Processor"

            @property
            def supported_extensions(self):
                return [".test"]

            def process(self, file_path, context):
                return ProcessorResult(success=True)

        processor = TestProcessor()
        namespace = processor.get_plugin_namespace()
        assert namespace == "my-test-processor"

    def test_configure_from_args(self, tmp_path):
        """Test configuring processor from arguments."""
        from imgc.plugin_api import FileProcessor, PluginArgument
        import argparse

        class ConfigurableProcessor(FileProcessor):
            def __init__(self):
                self.quality = 50  # Default value
                self.enabled = True

            @property
            def name(self):
                return "Configurable"

            @property
            def supported_extensions(self):
                return [".test"]

            def get_plugin_arguments(self):
                return [
                    PluginArgument("quality", int, 50, "Quality setting"),
                    PluginArgument("enabled", bool, True, "Enable processing"),
                ]

            def get_plugin_namespace(self):
                return "config"

            def process(self, file_path, context):
                return ProcessorResult(success=True)

        processor = ConfigurableProcessor()

        # Create mock args
        args = argparse.Namespace()
        args.config_quality = 90
        args.config_enabled = False

        # Configure processor
        processor.configure_from_args(args)

        # Check values were set
        assert processor.quality == 90
        assert processor.enabled is False

    def test_env_value_parsing(self, monkeypatch):
        """Test environment variable parsing."""
        from imgc.plugin_api import FileProcessor, PluginArgument

        class TestProcessor(FileProcessor):
            @property
            def name(self):
                return "Test"

            @property
            def supported_extensions(self):
                return [".test"]

            def process(self, file_path, context):
                return ProcessorResult(success=True)

        processor = TestProcessor()

        # Test different types
        int_arg = PluginArgument("int_val", int, 10)
        float_arg = PluginArgument("float_val", float, 1.5)
        bool_arg = PluginArgument("bool_val", bool, False)
        str_arg = PluginArgument("str_val", str, "default")

        # Set environment variables
        monkeypatch.setenv("IMGC_TEST_INT_VAL", "25")
        monkeypatch.setenv("IMGC_TEST_FLOAT_VAL", "3.14")
        monkeypatch.setenv("IMGC_TEST_BOOL_VAL", "true")
        monkeypatch.setenv("IMGC_TEST_STR_VAL", "custom")

        # Test parsing
        assert processor._get_env_value(int_arg, "test") == 25
        assert processor._get_env_value(float_arg, "test") == 3.14
        assert processor._get_env_value(bool_arg, "test") is True
        assert processor._get_env_value(str_arg, "test") == "custom"

        # Test bool false values
        monkeypatch.setenv("IMGC_TEST_BOOL_VAL", "false")
        assert processor._get_env_value(bool_arg, "test") is False

        # Test invalid values
        monkeypatch.setenv("IMGC_TEST_INT_VAL", "invalid")
        assert processor._get_env_value(int_arg, "test") is None
