"""
Shared pytest fixtures for imgc tests.

Provides common test utilities, sample data, and fixtures used across
multiple test modules.
"""

import pytest
import tempfile
from pathlib import Path
from PIL import Image
import sys

# Add imgc to path for all tests
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def sample_image_dir(tmp_path):
    """Create a directory with sample images in various formats."""
    image_dir = tmp_path / "sample_images"
    image_dir.mkdir()

    # Create sample images
    formats = [
        ("small.jpg", "JPEG", (50, 50), "red"),
        ("medium.png", "PNG", (100, 100), "green"),
        ("large.webp", "WEBP", (200, 200), "blue"),
    ]

    created_files = {}
    for filename, format_name, size, color in formats:
        file_path = image_dir / filename
        img = Image.new("RGB", size, color)
        save_kwargs = {}
        if format_name != "PNG":
            save_kwargs["quality"] = 95
        img.save(file_path, format_name, **save_kwargs)
        created_files[format_name.lower()] = file_path

    return image_dir, created_files


@pytest.fixture
def sample_plugin_dir(tmp_path):
    """Create a directory with sample test plugins."""
    plugin_dir = tmp_path / "test_plugins"
    plugin_dir.mkdir()

    # Create a simple test plugin
    plugin_file = plugin_dir / "test_processor.py"
    plugin_content = f"""
import sys
from pathlib import Path
sys.path.insert(0, "{tmp_path.parent.parent.parent}")

from imgc.plugin_api import FileProcessor, ProcessorResult

class TestProcessor(FileProcessor):
    @property
    def name(self):
        return "Test File Processor"
    
    @property
    def supported_extensions(self):
        return [".test", ".txt"]
    
    @property
    def priority(self):
        return 100
    
    def process(self, file_path, context):
        content = file_path.read_text() if file_path.suffix == ".txt" else "test content"
        word_count = len(content.split())
        
        return ProcessorResult(
            success=True,
            message=f"Processed {{file_path.name}}: {{word_count}} words",
            stats={{"word_count": word_count, "file_size": file_path.stat().st_size}},
            context={{"test_processor_ran": True}}
        )
"""
    plugin_file.write_text(plugin_content)

    return plugin_dir


@pytest.fixture
def mixed_file_dir(tmp_path):
    """Create a directory with mixed file types."""
    mixed_dir = tmp_path / "mixed_files"
    mixed_dir.mkdir()

    # Create various file types
    files = {}

    # Image files
    img = Image.new("RGB", (50, 50), "red")
    jpg_file = mixed_dir / "image.jpg"
    img.save(jpg_file, "JPEG")
    files["image"] = jpg_file

    # Text files
    txt_file = mixed_dir / "document.txt"
    txt_file.write_text("This is a sample document with multiple words for testing.")
    files["text"] = txt_file

    # Binary files
    bin_file = mixed_dir / "data.bin"
    bin_file.write_bytes(b"\\x00\\x01\\x02\\x03\\xFF\\xFE\\xFD")
    files["binary"] = bin_file

    # Log files
    log_file = mixed_dir / "application.log"
    log_content = """
2024-01-01 10:00:00 INFO Application started
2024-01-01 10:01:00 WARNING Configuration file not found, using defaults
2024-01-01 10:02:00 ERROR Failed to connect to database
2024-01-01 10:03:00 INFO Retrying database connection
2024-01-01 10:04:00 INFO Database connection established
"""
    log_file.write_text(log_content.strip())
    files["log"] = log_file

    return mixed_dir, files


@pytest.fixture
def temp_watch_dir(tmp_path):
    """Create a temporary directory suitable for watching."""
    watch_dir = tmp_path / "watch_directory"
    watch_dir.mkdir()
    return watch_dir


@pytest.fixture
def mock_plugin_processor():
    """Create a mock processor for testing."""
    from imgc.plugin_api import FileProcessor, ProcessorResult

    class MockProcessor(FileProcessor):
        def __init__(
            self,
            name="Mock Processor",
            extensions=None,
            priority=100,
            should_succeed=True,
        ):
            self._name = name
            self._extensions = extensions or [".mock"]
            self._priority = priority
            self._should_succeed = should_succeed
            self.call_count = 0
            self.last_file_path = None
            self.last_context = None

        @property
        def name(self):
            return self._name

        @property
        def supported_extensions(self):
            return self._extensions

        @property
        def priority(self):
            return self._priority

        def process(self, file_path, context):
            self.call_count += 1
            self.last_file_path = file_path
            self.last_context = context.copy()

            if self._should_succeed:
                return ProcessorResult(
                    success=True,
                    message=f"Mock processing of {file_path.name}",
                    stats={"mock_processed": True, "call_count": self.call_count},
                    context={"mock_processor_ran": True},
                )
            else:
                return ProcessorResult(success=False, message="Mock processor failed")

    return MockProcessor


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (slower)"
    )
    config.addinivalue_line("markers", "plugin: mark test as plugin-related test")
    config.addinivalue_line(
        "markers", "slow: mark test as slow (may take several seconds)"
    )
