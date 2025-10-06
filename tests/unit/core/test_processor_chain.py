"""
Tests for the ProcessorChain class.

Tests processor execution, timeout handling, error management, and chain coordination.
"""

import pytest
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from imgc.processor_chain import ProcessorChain
from imgc.plugin_manager import PluginManager
from imgc.plugin_api import FileProcessor, ProcessorResult, ProcessorTimeout


class TestProcessorChain:
    """Test the ProcessorChain class."""

    def test_init(self):
        """Test ProcessorChain initialization."""
        manager = PluginManager([])
        chain = ProcessorChain(manager, default_timeout=15.0, max_concurrent=2)

        assert chain.plugin_manager is manager
        assert chain.default_timeout == 15.0
        assert chain.max_concurrent == 2
        assert chain._stats["files_processed"] == 0

    def test_process_file_no_processors(self):
        """Test processing file with no applicable processors."""
        manager = PluginManager([])
        manager.processors = []  # No processors

        chain = ProcessorChain(manager)
        result = chain.process_file(Path("test.unknown"))

        assert result["success"] is True
        assert result["processors_run"] == 0
        assert result["results"] == []
        assert "No applicable processors found" in result["message"]

    def test_process_file_single_processor_success(self, tmp_path):
        """Test processing file with single successful processor."""

        class SuccessProcessor(FileProcessor):
            @property
            def name(self):
                return "Success Processor"

            @property
            def supported_extensions(self):
                return [".txt"]

            def process(self, file_path, context):
                return ProcessorResult(
                    success=True,
                    message="Successfully processed",
                    stats={"processed": True},
                    context={"success_processor_ran": True},
                )

        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello world")

        # Setup chain
        manager = PluginManager([])
        manager.processors = [SuccessProcessor()]
        chain = ProcessorChain(manager)

        # Process file
        result = chain.process_file(test_file)

        assert result["success"] is True
        assert result["processors_run"] == 1
        assert result["successful_processors"] == 1
        assert result["failed_processors"] == 0
        assert len(result["results"]) == 1

        proc_result = result["results"][0]
        assert proc_result["processor"] == "Success Processor"
        assert proc_result["success"] is True
        assert proc_result["result"]["success"] is True
        assert proc_result["result"]["message"] == "Successfully processed"

    def test_process_file_single_processor_failure(self, tmp_path):
        """Test processing file with single failing processor."""

        class FailProcessor(FileProcessor):
            @property
            def name(self):
                return "Fail Processor"

            @property
            def supported_extensions(self):
                return [".txt"]

            def process(self, file_path, context):
                return ProcessorResult(success=False, message="Processing failed")

        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello world")

        # Setup chain
        manager = PluginManager([])
        manager.processors = [FailProcessor()]
        chain = ProcessorChain(manager)

        # Process file
        result = chain.process_file(test_file)

        assert result["success"] is False  # Overall failure
        assert result["processors_run"] == 1
        assert result["successful_processors"] == 0
        assert result["failed_processors"] == 1

        proc_result = result["results"][0]
        assert proc_result["processor"] == "Fail Processor"
        assert proc_result["success"] is False

    def test_process_file_multiple_processors_priority(self, tmp_path):
        """Test processing file with multiple processors in priority order."""

        class HighPriorityProcessor(FileProcessor):
            @property
            def name(self):
                return "High Priority"

            @property
            def supported_extensions(self):
                return [".txt"]

            @property
            def priority(self):
                return 10  # Lower number = higher priority

            def process(self, file_path, context):
                return ProcessorResult(
                    success=True,
                    message="High priority processed",
                    context={"high_priority_ran": True},
                )

        class LowPriorityProcessor(FileProcessor):
            @property
            def name(self):
                return "Low Priority"

            @property
            def supported_extensions(self):
                return [".txt"]

            @property
            def priority(self):
                return 100  # Higher number = lower priority

            def process(self, file_path, context):
                # Check that high priority processor ran first via context
                if "high_priority_ran" not in context:
                    return ProcessorResult(
                        success=False,
                        message="High priority processor should have run first",
                    )
                return ProcessorResult(success=True, message="Low priority processed")

        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello world")

        # Setup chain (add in reverse order to test sorting)
        manager = PluginManager([])
        manager.processors = [LowPriorityProcessor(), HighPriorityProcessor()]
        chain = ProcessorChain(manager)

        # Process file
        result = chain.process_file(test_file)

        assert result["success"] is True
        assert result["processors_run"] == 2
        assert result["successful_processors"] == 2

        # Check execution order
        assert result["results"][0]["processor"] == "High Priority"
        assert result["results"][0]["order"] == 1
        assert result["results"][1]["processor"] == "Low Priority"
        assert result["results"][1]["order"] == 2

    def test_process_file_timeout(self, tmp_path):
        """Test processor timeout handling."""

        class SlowProcessor(FileProcessor):
            @property
            def name(self):
                return "Slow Processor"

            @property
            def supported_extensions(self):
                return [".txt"]

            def process(self, file_path, context):
                time.sleep(2.0)  # Sleep longer than timeout
                return ProcessorResult(success=True, message="Finally done")

        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello world")

        # Setup chain with short timeout
        manager = PluginManager([])
        manager.processors = [SlowProcessor()]
        chain = ProcessorChain(manager, default_timeout=0.5)  # 0.5 second timeout

        # Process file
        result = chain.process_file(test_file)

        assert result["success"] is False  # Overall failure due to timeout
        assert result["processors_run"] == 1
        assert result["failed_processors"] == 1

        proc_result = result["results"][0]
        assert proc_result["processor"] == "Slow Processor"
        assert proc_result["success"] is False
        assert "timeout" in proc_result["result"]

    def test_process_file_exception_handling(self, tmp_path):
        """Test processor exception handling."""

        class ExceptionProcessor(FileProcessor):
            @property
            def name(self):
                return "Exception Processor"

            @property
            def supported_extensions(self):
                return [".txt"]

            def process(self, file_path, context):
                raise ValueError("Something went wrong!")

        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello world")

        # Setup chain
        manager = PluginManager([])
        manager.processors = [ExceptionProcessor()]
        chain = ProcessorChain(manager)

        # Process file
        result = chain.process_file(test_file)

        assert result["success"] is False
        assert result["processors_run"] == 1
        assert result["failed_processors"] == 1

        proc_result = result["results"][0]
        assert proc_result["processor"] == "Exception Processor"
        assert proc_result["success"] is False
        assert "Something went wrong!" in proc_result["result"]["message"]

    def test_process_multiple_files(self, tmp_path):
        """Test processing multiple files."""

        class CounterProcessor(FileProcessor):
            def __init__(self):
                self.count = 0

            @property
            def name(self):
                return "Counter Processor"

            @property
            def supported_extensions(self):
                return [".txt"]

            def process(self, file_path, context):
                self.count += 1
                return ProcessorResult(
                    success=True,
                    message=f"Processed file #{self.count}",
                    stats={"count": self.count},
                )

        # Create test files
        files = []
        for i in range(3):
            test_file = tmp_path / f"test{i}.txt"
            test_file.write_text(f"Content {i}")
            files.append(test_file)

        # Setup chain
        processor = CounterProcessor()
        manager = PluginManager([])
        manager.processors = [processor]
        chain = ProcessorChain(manager)

        # Process multiple files
        results = chain.process_multiple_files(files)

        assert len(results) == 3
        assert all(r["success"] for r in results)
        assert processor.count == 3

    def test_get_stats(self):
        """Test chain statistics."""
        manager = PluginManager([])
        chain = ProcessorChain(manager)

        stats = chain.get_stats()

        expected_keys = [
            "files_processed",
            "total_processors_run",
            "successful_processors",
            "failed_processors",
            "timeouts",
        ]

        for key in expected_keys:
            assert key in stats
            assert stats[key] == 0  # Initially zero

    def test_reset_stats(self):
        """Test resetting chain statistics."""
        manager = PluginManager([])
        chain = ProcessorChain(manager)

        # Manually set some stats
        chain._stats["files_processed"] = 5
        chain._stats["successful_processors"] = 10

        # Reset
        chain.reset_stats()

        stats = chain.get_stats()
        assert stats["files_processed"] == 0
        assert stats["successful_processors"] == 0

    def test_is_supported_file(self):
        """Test checking if file is supported."""

        class TxtProcessor(FileProcessor):
            @property
            def name(self):
                return "Text Processor"

            @property
            def supported_extensions(self):
                return [".txt"]

            def process(self, file_path, context):
                return ProcessorResult(success=True, message="OK")

        manager = PluginManager([])
        manager.processors = [TxtProcessor()]
        chain = ProcessorChain(manager)

        assert chain.is_supported_file(Path("test.txt"))
        assert not chain.is_supported_file(Path("image.jpg"))

    def test_list_processors_for_file(self):
        """Test listing processors for a specific file."""

        class Processor1(FileProcessor):
            @property
            def name(self):
                return "Processor One"

            @property
            def supported_extensions(self):
                return [".txt"]

            @property
            def priority(self):
                return 50

            def process(self, file_path, context):
                return ProcessorResult(success=True, message="OK")

        class Processor2(FileProcessor):
            @property
            def name(self):
                return "Processor Two"

            @property
            def supported_extensions(self):
                return [".txt", ".md"]

            @property
            def priority(self):
                return 25

            def process(self, file_path, context):
                return ProcessorResult(success=True, message="OK")

        manager = PluginManager([])
        manager.processors = [Processor1(), Processor2()]
        chain = ProcessorChain(manager)

        processors = chain.list_processors_for_file(Path("test.txt"))

        assert len(processors) == 2
        # Should be sorted by priority
        assert processors[0]["name"] == "Processor Two"  # Priority 25
        assert processors[0]["priority"] == 25
        assert processors[1]["name"] == "Processor One"  # Priority 50
        assert processors[1]["priority"] == 50
