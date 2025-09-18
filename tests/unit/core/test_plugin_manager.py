"""
Tests for the PluginManager class.

Tests plugin discovery, loading, validation, and management functionality.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from imgc.plugin_manager import PluginManager
from imgc.plugin_api import FileProcessor, ProcessorResult, ProcessorValidationError


class TestPluginManager:
    """Test the PluginManager class."""

    def test_init_default_dirs(self):
        """Test PluginManager initialization with default directories."""
        manager = PluginManager()

        # Should have default plugin directories
        assert len(manager.plugin_dirs) > 0

        # Should include builtin plugins
        builtin_found = any("builtin" in str(d) for d in manager.plugin_dirs)
        assert builtin_found

        # Should include local plugins directory (next to executable/main.py)
        # The exact path depends on how tests are run, but should contain "plugins"
        plugin_dirs_str = [str(d) for d in manager.plugin_dirs]
        assert any("plugins" in d for d in plugin_dirs_str)

    def test_init_custom_dirs(self):
        """Test PluginManager with custom directories."""
        custom_dirs = [Path("/custom/plugins"), Path("/another/dir")]
        manager = PluginManager(custom_dirs)

        # Should include custom dirs plus built-in plugins
        assert len(manager.plugin_dirs) == len(custom_dirs) + 1  # +1 for built-in

        # Should contain all custom directories
        for custom_dir in custom_dirs:
            assert custom_dir in manager.plugin_dirs

        # Should always include built-in plugins
        builtin_found = any("builtin" in str(d) for d in manager.plugin_dirs)
        assert builtin_found
        assert len(manager.processors) == 0
        assert len(manager.failed_plugins) == 0

    def test_create_plugin_directories(self, tmp_path):
        """Test creating plugin directories."""
        plugin_dir = tmp_path / "test_plugins"
        manager = PluginManager([plugin_dir])

        # Directory shouldn't exist initially
        assert not plugin_dir.exists()

        # Create directories
        manager.create_plugin_directories()

        # Directory should now exist
        assert plugin_dir.exists()
        assert plugin_dir.is_dir()

    def test_discover_plugins_empty_dir(self, tmp_path):
        """Test plugin discovery in empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        manager = PluginManager([empty_dir])
        manager.discover_plugins()

        # Should have 1 processor (built-in ImageProcessor)
        assert len(manager.processors) == 1
        assert len(manager.failed_plugins) == 0

        # The processor should be the built-in ImageProcessor
        assert manager.processors[0].name == "Image Compressor"

    def test_discover_plugins_with_valid_plugin(self, tmp_path):
        """Test discovering a valid plugin."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        # Create a valid plugin file
        plugin_file = plugin_dir / "test_plugin.py"
        plugin_content = """
from pathlib import Path
import sys

# Add imgc to path (simulate user plugin)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from imgc.plugin_api import FileProcessor, ProcessorResult

class TestFileProcessor(FileProcessor):
    @property
    def name(self):
        return "Test Plugin"
    
    @property
    def supported_extensions(self):
        return [".test"]
    
    def process(self, file_path, context):
        return ProcessorResult(success=True, message="Test successful")
"""
        plugin_file.write_text(plugin_content)

        manager = PluginManager([plugin_dir])
        manager.discover_plugins()

        # Should have 2 processors: built-in ImageProcessor + test plugin
        assert len(manager.processors) == 2
        assert len(manager.failed_plugins) == 0

        # Find the test plugin
        test_plugin = None
        for processor in manager.processors:
            if processor.name == "Test Plugin":
                test_plugin = processor
                break

        assert test_plugin is not None
        assert test_plugin.supported_extensions == [".test"]

    def test_discover_plugins_with_invalid_syntax(self, tmp_path):
        """Test discovering plugin with syntax errors."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        # Create plugin with syntax error
        plugin_file = plugin_dir / "bad_syntax.py"
        plugin_content = """
def invalid_syntax(
    # Missing closing parenthesis
    return "broken"
"""
        plugin_file.write_text(plugin_content)

        manager = PluginManager([plugin_dir])
        manager.discover_plugins()

        # Should have 1 processor (built-in ImageProcessor), syntax error plugin should fail
        assert len(manager.processors) == 1
        assert len(manager.failed_plugins) == 1
        assert "bad_syntax.py" in manager.failed_plugins
        assert manager.processors[0].name == "Image Compressor"
        assert "Syntax error" in manager.failed_plugins["bad_syntax.py"]

    def test_discover_plugins_with_invalid_processor(self, tmp_path):
        """Test discovering plugin with invalid processor class."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        # Create plugin with invalid processor
        plugin_file = plugin_dir / "invalid_processor.py"
        plugin_content = """
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from imgc.plugin_api import FileProcessor, ProcessorResult

class InvalidProcessor(FileProcessor):
    @property
    def name(self):
        return ""  # Invalid: empty name
    
    @property
    def supported_extensions(self):
        return []  # Invalid: empty extensions
    
    def process(self, file_path, context):
        return ProcessorResult(success=True, message="OK")
"""
        plugin_file.write_text(plugin_content)

        manager = PluginManager([plugin_dir])
        manager.discover_plugins()

        # Should have 1 processor (built-in ImageProcessor), invalid plugin should fail
        assert len(manager.processors) == 1
        assert len(manager.failed_plugins) == 1
        assert "invalid_processor.py" in manager.failed_plugins
        assert manager.processors[0].name == "Image Compressor"

    def test_discover_plugins_ignores_private_files(self, tmp_path):
        """Test that private files (starting with _) are ignored."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        # Create private file
        private_file = plugin_dir / "_private.py"
        private_file.write_text("# This should be ignored")

        # Create __init__.py
        init_file = plugin_dir / "__init__.py"
        init_file.write_text("# This should be ignored")

        manager = PluginManager([plugin_dir])
        manager.discover_plugins()

        # Should have 1 processor (built-in ImageProcessor), private files ignored
        assert len(manager.processors) == 1
        assert len(manager.failed_plugins) == 0
        assert manager.processors[0].name == "Image Compressor"

    def test_get_processors_for_file(self, tmp_path):
        """Test getting processors for specific files."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        # Create plugin that handles .txt files
        plugin_file = plugin_dir / "text_processor.py"
        plugin_content = """
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from imgc.plugin_api import FileProcessor, ProcessorResult

class TextProcessor(FileProcessor):
    @property
    def name(self):
        return "Text Processor"
    
    @property
    def supported_extensions(self):
        return [".txt", ".md"]
    
    @property
    def priority(self):
        return 50
    
    def process(self, file_path, context):
        return ProcessorResult(success=True, message="Processed text")
"""
        plugin_file.write_text(plugin_content)

        manager = PluginManager([plugin_dir])
        manager.discover_plugins()

        # Test file matching
        txt_processors = manager.get_processors_for_file(Path("test.txt"))
        assert len(txt_processors) == 1
        assert txt_processors[0].name == "Text Processor"

        md_processors = manager.get_processors_for_file(Path("README.md"))
        assert len(md_processors) == 1

        jpg_processors = manager.get_processors_for_file(Path("image.jpg"))
        assert len(jpg_processors) == 0

    def test_get_processor_by_name(self, tmp_path):
        """Test getting processor by name."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        # Create plugin
        plugin_file = plugin_dir / "named_processor.py"
        plugin_content = """
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from imgc.plugin_api import FileProcessor, ProcessorResult

class NamedProcessor(FileProcessor):
    @property
    def name(self):
        return "Unique Processor Name"
    
    @property
    def supported_extensions(self):
        return [".unique"]
    
    def process(self, file_path, context):
        return ProcessorResult(success=True, message="OK")
"""
        plugin_file.write_text(plugin_content)

        manager = PluginManager([plugin_dir])
        manager.discover_plugins()

        # Test finding by name
        processor = manager.get_processor_by_name("Unique Processor Name")
        assert processor is not None
        assert processor.name == "Unique Processor Name"

        # Test not finding
        missing = manager.get_processor_by_name("Non-existent Processor")
        assert missing is None

    def test_get_supported_extensions(self, tmp_path):
        """Test getting all supported extensions."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        # Create multiple plugins with different extensions
        plugin1_file = plugin_dir / "plugin1.py"
        plugin1_content = """
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from imgc.plugin_api import FileProcessor, ProcessorResult

class Plugin1(FileProcessor):
    @property
    def name(self):
        return "Plugin 1"
    
    @property
    def supported_extensions(self):
        return [".txt", ".md"]
    
    def process(self, file_path, context):
        return ProcessorResult(success=True, message="OK")
"""
        plugin1_file.write_text(plugin1_content)

        plugin2_file = plugin_dir / "plugin2.py"
        plugin2_content = """
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from imgc.plugin_api import FileProcessor, ProcessorResult

class Plugin2(FileProcessor):
    @property
    def name(self):
        return "Plugin 2"
    
    @property
    def supported_extensions(self):
        return [".jpg", ".png", ".txt"]  # .txt overlaps with plugin1
    
    def process(self, file_path, context):
        return ProcessorResult(success=True, message="OK")
"""
        plugin2_file.write_text(plugin2_content)

        manager = PluginManager([plugin_dir])
        manager.discover_plugins()

        extensions = manager.get_supported_extensions()

        # Should be sorted and unique, including built-in image processor extensions
        expected = [".avif", ".jpeg", ".jpg", ".md", ".png", ".txt", ".webp"]
        assert extensions == expected

    def test_get_stats(self, tmp_path):
        """Test getting manager statistics."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        # Create one valid and one invalid plugin
        valid_file = plugin_dir / "valid.py"
        valid_content = """
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from imgc.plugin_api import FileProcessor, ProcessorResult

class ValidProcessor(FileProcessor):
    @property
    def name(self):
        return "Valid Processor"
    
    @property
    def supported_extensions(self):
        return [".valid"]
    
    def process(self, file_path, context):
        return ProcessorResult(success=True, message="OK")
"""
        valid_file.write_text(valid_content)

        invalid_file = plugin_dir / "invalid.py"
        invalid_file.write_text("invalid python syntax (")

        manager = PluginManager([plugin_dir])
        manager.discover_plugins()

        stats = manager.get_stats()

        # Should have 2 processors: built-in ImageProcessor + valid plugin
        assert stats["total_processors"] == 2
        assert stats["failed_plugins"] == 1
        # Should have 6 unique extensions: .valid + 5 from ImageProcessor (.jpg, .jpeg, .png, .webp, .avif)
        assert stats["supported_extensions"] == 6
        assert len(stats["processors"]) == 2

        # Find the valid processor in the stats
        valid_processor_found = any(
            p["name"] == "Valid Processor" for p in stats["processors"]
        )
        image_processor_found = any(
            p["name"] == "Image Compressor" for p in stats["processors"]
        )
        assert valid_processor_found
        assert image_processor_found
        assert "invalid.py" in stats["failed"]

    def test_reload_plugins(self, tmp_path):
        """Test reloading plugins."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        manager = PluginManager([plugin_dir])

        # Initially only built-in plugins
        manager.discover_plugins()
        assert len(manager.processors) == 1  # Built-in ImageProcessor

        # Add a plugin
        plugin_file = plugin_dir / "new_plugin.py"
        plugin_content = """
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from imgc.plugin_api import FileProcessor, ProcessorResult

class NewProcessor(FileProcessor):
    @property
    def name(self):
        return "New Processor"
    
    @property
    def supported_extensions(self):
        return [".new"]
    
    def process(self, file_path, context):
        return ProcessorResult(success=True, message="OK")
"""
        plugin_file.write_text(plugin_content)

        # Reload should find the new plugin
        manager.reload_plugins()
        assert len(manager.processors) == 2  # Built-in + new plugin

        # Find the new plugin
        new_plugin_found = any(p.name == "New Processor" for p in manager.processors)
        image_processor_found = any(
            p.name == "Image Compressor" for p in manager.processors
        )
        assert new_plugin_found
        assert image_processor_found


class TestPluginValidation:
    """Test plugin validation logic."""

    def test_validate_plugin_syntax_valid(self, tmp_path):
        """Test syntax validation with valid Python."""
        plugin_file = tmp_path / "valid.py"
        plugin_file.write_text("def hello(): return 'world'")

        manager = PluginManager([])
        # Should not raise
        manager._validate_plugin_syntax(plugin_file)

    def test_validate_plugin_syntax_invalid(self, tmp_path):
        """Test syntax validation with invalid Python."""
        plugin_file = tmp_path / "invalid.py"
        plugin_file.write_text("def broken(: return 'syntax error'")

        manager = PluginManager([])

        with pytest.raises(ProcessorValidationError) as exc_info:
            manager._validate_plugin_syntax(plugin_file)

        assert "Syntax error" in str(exc_info.value)

    def test_validate_processor_valid(self):
        """Test processor validation with valid processor."""

        class ValidProcessor(FileProcessor):
            @property
            def name(self):
                return "Valid Test Processor"

            @property
            def supported_extensions(self):
                return [".txt", ".md"]

            def process(self, file_path, context):
                return ProcessorResult(success=True, message="OK")

        manager = PluginManager([])
        processor = ValidProcessor()

        # Should not raise
        manager._validate_processor(processor, Path("test.py"))

    def test_validate_processor_invalid_name(self):
        """Test processor validation with invalid name."""

        class InvalidProcessor(FileProcessor):
            @property
            def name(self):
                return ""  # Invalid: empty name

            @property
            def supported_extensions(self):
                return [".txt"]

            def process(self, file_path, context):
                return ProcessorResult(success=True, message="OK")

        manager = PluginManager([])
        processor = InvalidProcessor()

        with pytest.raises(ProcessorValidationError) as exc_info:
            manager._validate_processor(processor, Path("test.py"))

        assert "name must be a non-empty string" in str(exc_info.value)

    def test_validate_processor_invalid_extensions(self):
        """Test processor validation with invalid extensions."""

        class InvalidProcessor(FileProcessor):
            @property
            def name(self):
                return "Invalid Extensions Processor"

            @property
            def supported_extensions(self):
                return ["txt", ".md"]  # Invalid: missing dot

            def process(self, file_path, context):
                return ProcessorResult(success=True, message="OK")

        manager = PluginManager([])
        processor = InvalidProcessor()

        with pytest.raises(ProcessorValidationError) as exc_info:
            manager._validate_processor(processor, Path("test.py"))

        assert "must start with '.'" in str(exc_info.value)

    def test_get_all_plugin_arguments(self, tmp_path):
        """Test collecting arguments from all plugins."""
        from imgc.plugin_api import PluginArgument

        # Create plugin with arguments
        plugin_content = """
from imgc.plugin_api import FileProcessor, ProcessorResult, PluginArgument

class TestProcessor(FileProcessor):
    @property
    def name(self):
        return "Test Processor"
    
    @property
    def supported_extensions(self):
        return [".test"]
    
    def get_plugin_arguments(self):
        return [
            PluginArgument("quality", int, 80, "Quality setting"),
            PluginArgument("enabled", bool, True, "Enable processing")
        ]
    
    def get_plugin_namespace(self):
        return "test"
    
    def process(self, file_path, context):
        return ProcessorResult(success=True, message="Test processed")
"""

        plugin_file = tmp_path / "test_plugin.py"
        plugin_file.write_text(plugin_content)

        manager = PluginManager([tmp_path])
        manager.discover_plugins()

        # Get all plugin arguments
        all_args = manager.get_all_plugin_arguments()

        assert "test" in all_args
        args = all_args["test"]
        assert len(args) == 2

        arg_names = [arg.name for arg in args]
        assert "quality" in arg_names
        assert "enabled" in arg_names

    def test_configure_plugins_from_args(self, tmp_path):
        """Test configuring plugins from parsed arguments."""
        import argparse

        # Create plugin with arguments
        plugin_content = """
from imgc.plugin_api import FileProcessor, ProcessorResult, PluginArgument

class ConfigurableProcessor(FileProcessor):
    def __init__(self):
        self.quality = 50
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
            PluginArgument("enabled", bool, True, "Enable processing")
        ]
    
    def get_plugin_namespace(self):
        return "config"
    
    def process(self, file_path, context):
        return ProcessorResult(success=True)
"""

        plugin_file = tmp_path / "configurable_plugin.py"
        plugin_file.write_text(plugin_content)

        manager = PluginManager([tmp_path])
        manager.discover_plugins()

        # Create mock args
        args = argparse.Namespace()
        args.config_quality = 95
        args.config_enabled = False

        # Configure plugins
        manager.configure_plugins_from_args(args)

        # Check that processor was configured
        processor = manager.get_processor_by_name("Configurable")
        assert processor is not None
        assert processor.quality == 95
        assert processor.enabled is False
