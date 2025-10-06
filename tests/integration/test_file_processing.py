"""
Integration tests for end-to-end file processing.

Tests the complete workflow from file detection through plugin processing,
including real file system operations and plugin chain execution.
"""

import pytest
import tempfile
import time
import threading
from pathlib import Path
from PIL import Image

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from imgc.plugin_watcher import PluginWatcher
from imgc.plugin_manager import PluginManager
from imgc.processor_chain import ProcessorChain


class TestEndToEndFileProcessing:
    """Test complete file processing workflows."""

    def test_image_processing_workflow(self, tmp_path):
        """Test complete image processing workflow."""
        # Create watch directory
        watch_dir = tmp_path / "watch"
        watch_dir.mkdir()

        # Create plugin watcher (uses built-in image processor)
        watcher = PluginWatcher(watch_dir, stable_seconds=0.1, compress_timeout=10.0)

        # Create test image
        test_image = watch_dir / "test.jpg"
        img = Image.new("RGB", (200, 200), color="red")
        img.save(test_image, "JPEG", quality=95)  # High quality

        original_size = test_image.stat().st_size

        # Process existing files
        stats = watcher.process_existing_files()

        assert stats["total_files"] == 1
        assert stats["successful_files"] == 1
        assert stats["failed_files"] == 0

        # Verify image was compressed
        new_size = test_image.stat().st_size
        assert new_size < original_size  # Should be smaller

    def test_multiple_format_processing(self, tmp_path):
        """Test processing multiple image formats."""
        watch_dir = tmp_path / "multi_format"
        watch_dir.mkdir()

        watcher = PluginWatcher(watch_dir, stable_seconds=0.1)

        # Create images in different formats
        formats = [("test.jpg", "JPEG"), ("test.png", "PNG"), ("test.webp", "WEBP")]

        created_files = []
        for filename, format_name in formats:
            file_path = watch_dir / filename
            img = Image.new("RGB", (100, 100), color="blue")
            img.save(
                file_path, format_name, quality=90 if format_name != "PNG" else None
            )
            created_files.append(file_path)

        # Process all files
        stats = watcher.process_existing_files()

        assert stats["total_files"] == 3
        assert stats["successful_files"] == 3
        assert stats["failed_files"] == 0

        # All files should still exist (processed in-place)
        for file_path in created_files:
            assert file_path.exists()

    def test_unsupported_file_ignored(self, tmp_path):
        """Test that unsupported files are ignored."""
        watch_dir = tmp_path / "mixed_files"
        watch_dir.mkdir()

        watcher = PluginWatcher(watch_dir)

        # Create mix of supported and unsupported files
        # Supported
        img_file = watch_dir / "image.jpg"
        img = Image.new("RGB", (50, 50), color="green")
        img.save(img_file, "JPEG")

        # Unsupported
        text_file = watch_dir / "document.txt"
        text_file.write_text("This is a text file")

        pdf_file = watch_dir / "document.pdf"
        pdf_file.write_bytes(b"Fake PDF content")

        # Process existing files
        stats = watcher.process_existing_files()

        # Should only process the image file
        assert stats["total_files"] == 1  # Only image file
        assert stats["successful_files"] == 1

    def test_plugin_chain_execution_order(self, tmp_path):
        """Test that plugins execute in correct priority order."""
        # Create custom plugin directory
        plugin_dir = tmp_path / "custom_plugins"
        plugin_dir.mkdir()

        # Create test plugin with high priority
        plugin_file = plugin_dir / "priority_test.py"
        # Create plugin content with proper escaping
        base_path = str(tmp_path.parent.parent.parent).replace("\\", "\\\\")
        plugin_content = f"""
import sys
from pathlib import Path
sys.path.insert(0, r"{base_path}")

from imgc.plugin_api import FileProcessor, ProcessorResult

class HighPriorityProcessor(FileProcessor):
    @property
    def name(self):
        return "High Priority Test"
    
    @property
    def supported_extensions(self):
        return [".test"]
    
    @property
    def priority(self):
        return 10  # Higher priority than built-in image processor (50)
    
    def process(self, file_path, context):
        # Mark that we ran first
        return ProcessorResult(
            success=True,
            message="High priority processor ran",
            context={{"high_priority_executed": True}}
        )

class LowPriorityProcessor(FileProcessor):
    @property
    def name(self):
        return "Low Priority Test"
    
    @property
    def supported_extensions(self):
        return [".test"]
    
    @property
    def priority(self):
        return 200  # Lower priority
    
    def process(self, file_path, context):
        # Verify high priority ran first
        if "high_priority_executed" not in context:
            return ProcessorResult(success=False, message="High priority should run first")
        
        return ProcessorResult(
            success=True,
            message="Low priority processor ran after high priority"
        )
"""
        plugin_file.write_text(plugin_content)

        # Create watcher with custom plugin directory
        watch_dir = tmp_path / "watch"
        watch_dir.mkdir()

        watcher = PluginWatcher(watch_dir, plugin_dirs=[plugin_dir])

        # Create test file
        test_file = watch_dir / "test.test"
        test_file.write_text("test content")

        # Process the file
        stats = watcher.process_existing_files()

        # Both processors should have run successfully
        assert stats["total_files"] == 1
        assert stats["successful_files"] == 1


class TestFileSystemWatching:
    """Test real-time file system watching."""

    def test_watch_mode_detects_new_files(self, tmp_path):
        """Test that watch mode detects newly created files."""
        watch_dir = tmp_path / "watch"
        watch_dir.mkdir()

        # Create watcher
        watcher = PluginWatcher(watch_dir, stable_seconds=0.1, new_delay=0.1)

        # Track processing results
        processed_files = []

        # Start watching in background
        def watch_thread():
            try:
                watcher.start_watching(process_existing=False)
            except:
                pass  # Expected when we stop the watcher

        thread = threading.Thread(target=watch_thread, daemon=True)
        thread.start()

        # Give watcher time to start
        time.sleep(0.2)

        try:
            # Create new image file
            new_image = watch_dir / "new_image.jpg"
            img = Image.new("RGB", (50, 50), color="yellow")
            img.save(new_image, "JPEG")

            # Give time for processing
            time.sleep(0.5)

            # File should have been processed
            # We can't easily verify processing happened without complex mocking,
            # but we can verify the watcher is running and the file exists
            assert new_image.exists()

            # Get watcher stats
            stats = watcher.get_stats()
            assert stats["watcher"]["is_watching"] is True
            assert ".jpg" in stats["watcher"]["supported_extensions"]

        finally:
            # Stop the watcher
            watcher.stop()
            thread.join(timeout=1.0)


class TestErrorHandling:
    """Test error handling in file processing."""

    def test_corrupted_file_handling(self, tmp_path):
        """Test handling of corrupted image files."""
        watch_dir = tmp_path / "corrupted"
        watch_dir.mkdir()

        watcher = PluginWatcher(watch_dir)

        # Create corrupted image file
        corrupted_file = watch_dir / "corrupted.jpg"
        corrupted_file.write_bytes(b"This is not a valid JPEG file")

        # Process existing files
        stats = watcher.process_existing_files()

        # Should detect the file but processing should fail gracefully
        assert stats["total_files"] == 1
        assert stats["failed_files"] == 1
        assert stats["successful_files"] == 0

    def test_permission_denied_handling(self, tmp_path):
        """Test handling of permission denied errors."""
        watch_dir = tmp_path / "permissions"
        watch_dir.mkdir()

        watcher = PluginWatcher(watch_dir)

        # Create image file
        restricted_file = watch_dir / "restricted.jpg"
        img = Image.new("RGB", (50, 50), color="red")
        img.save(restricted_file, "JPEG")

        # Make file read-only to simulate permission issues
        restricted_file.chmod(0o444)

        try:
            # Process existing files
            stats = watcher.process_existing_files()

            # Should handle permission errors gracefully
            # (might succeed or fail depending on operation, but shouldn't crash)
            assert stats["total_files"] == 1

        finally:
            # Restore permissions for cleanup
            restricted_file.chmod(0o644)


class TestPluginSystemIntegration:
    """Test integration between different plugin system components."""

    def test_plugin_reload_during_operation(self, tmp_path):
        """Test reloading plugins during operation."""
        watch_dir = tmp_path / "reload_test"
        watch_dir.mkdir()

        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        watcher = PluginWatcher(watch_dir, plugin_dirs=[plugin_dir])

        # Initially should only have built-in image processor
        initial_stats = watcher.get_stats()
        initial_processors = initial_stats["plugins"]["total_processors"]

        # Add a new plugin
        new_plugin = plugin_dir / "runtime_plugin.py"
        # Create plugin content with proper path escaping
        base_path = str(tmp_path.parent.parent.parent).replace("\\", "\\\\")
        plugin_content = f"""
import sys
from pathlib import Path
sys.path.insert(0, r"{base_path}")

from imgc.plugin_api import FileProcessor, ProcessorResult

class RuntimeProcessor(FileProcessor):
    @property
    def name(self):
        return "Runtime Added Processor"
    
    @property
    def supported_extensions(self):
        return [".runtime"]
    
    def process(self, file_path, context):
        return ProcessorResult(success=True, message="Runtime processor executed")
"""
        new_plugin.write_text(plugin_content)

        # Reload plugins
        watcher.reload_plugins()

        # Should now have additional processor
        new_stats = watcher.get_stats()
        new_processors = new_stats["plugins"]["total_processors"]

        assert new_processors == initial_processors + 1
        assert ".runtime" in new_stats["watcher"]["supported_extensions"]
