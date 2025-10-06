"""
Processor Chain for imgc - Executes file processors in sequence with timeout and error handling.

This module provides the execution environment for running file processors
safely with proper timeout handling, resource management, and result aggregation.
"""

import threading
import time
import signal
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
import logging
from contextlib import contextmanager

from .plugin_api import FileProcessor, ProcessorResult, ProcessorError, ProcessorTimeout
from .plugin_manager import PluginManager

logger = logging.getLogger(__name__)


class ProcessorChain:
    """
    Executes a chain of file processors with proper error handling and timeouts.

    The ProcessorChain takes a file and runs it through all applicable processors
    in priority order, collecting results and handling errors gracefully.
    """

    def __init__(
        self,
        plugin_manager: PluginManager,
        default_timeout: float = 30.0,
        max_concurrent: int = 1,
    ):
        """
        Initialize the processor chain.

        Args:
            plugin_manager: Manager containing loaded processors
            default_timeout: Default timeout per processor in seconds
            max_concurrent: Maximum number of concurrent processor executions
        """
        self.plugin_manager = plugin_manager
        self.default_timeout = default_timeout
        self.max_concurrent = max_concurrent
        self._semaphore = threading.Semaphore(max_concurrent)
        self._stats = {
            "files_processed": 0,
            "total_processors_run": 0,
            "successful_processors": 0,
            "failed_processors": 0,
            "timeouts": 0,
        }

    def process_file(
        self,
        file_path: Path,
        timeout: Optional[float] = None,
        processor_filter: Optional[Callable[[FileProcessor], bool]] = None,
    ) -> Dict[str, Any]:
        """
        Process a file through the applicable processor chain.

        Args:
            file_path: Path to the file to process
            timeout: Timeout per processor (uses default if None)
            processor_filter: Optional function to filter which processors to run

        Returns:
            Dict containing processing results and metadata
        """
        start_time = time.time()
        timeout = timeout or self.default_timeout

        logger.debug(f"Processing file: {file_path}")

        # Get applicable processors
        processors = self.plugin_manager.get_processors_for_file(file_path)

        if processor_filter:
            processors = [p for p in processors if processor_filter(p)]

        if not processors:
            logger.debug(f"No processors found for {file_path}")
            return {
                "file_path": str(file_path),
                "processors_run": 0,
                "results": [],
                "success": True,
                "message": "No applicable processors found",
                "duration": time.time() - start_time,
            }

        logger.debug(
            f"Found {len(processors)} processors for {file_path}: "
            f"{[p.name for p in processors]}"
        )

        # Execute processor chain
        results = []
        context = {"original_path": file_path, "chain_start_time": start_time}
        overall_success = True

        with self._semaphore:
            for i, processor in enumerate(processors):
                try:
                    logger.debug(
                        f"Running processor {i+1}/{len(processors)}: {processor.name}"
                    )

                    result = self._execute_processor(
                        processor, file_path, context, timeout
                    )
                    results.append(
                        {
                            "processor": processor.name,
                            "processor_version": processor.version,
                            "result": result.to_dict(),
                            "success": result.success,
                            "order": i + 1,
                        }
                    )

                    # Update context for next processor
                    if result.success and result.context:
                        context.update(result.context)

                    # Update stats
                    self._stats["total_processors_run"] += 1
                    if result.success:
                        self._stats["successful_processors"] += 1
                    else:
                        self._stats["failed_processors"] += 1
                        overall_success = False

                except ProcessorTimeout as e:
                    logger.warning(f"Processor {processor.name} timed out: {e}")
                    results.append(
                        {
                            "processor": processor.name,
                            "processor_version": processor.version,
                            "result": {
                                "success": False,
                                "message": str(e),
                                "timeout": True,
                            },
                            "success": False,
                            "order": i + 1,
                        }
                    )
                    self._stats["timeouts"] += 1
                    self._stats["failed_processors"] += 1
                    overall_success = False

                except Exception as e:
                    logger.error(f"Processor {processor.name} failed: {e}")
                    results.append(
                        {
                            "processor": processor.name,
                            "processor_version": processor.version,
                            "result": {
                                "success": False,
                                "message": str(e),
                                "error": True,
                            },
                            "success": False,
                            "order": i + 1,
                        }
                    )
                    self._stats["failed_processors"] += 1
                    overall_success = False

        self._stats["files_processed"] += 1

        duration = time.time() - start_time
        successful_count = sum(1 for r in results if r["success"])

        return {
            "file_path": str(file_path),
            "processors_run": len(processors),
            "successful_processors": successful_count,
            "failed_processors": len(processors) - successful_count,
            "results": results,
            "success": overall_success,
            "message": f"Processed through {len(processors)} processors",
            "duration": duration,
        }

    def _execute_processor(
        self,
        processor: FileProcessor,
        file_path: Path,
        context: Dict[str, Any],
        timeout: float,
    ) -> ProcessorResult:
        """
        Execute a single processor with timeout handling.

        Args:
            processor: The processor to execute
            file_path: File to process
            context: Context from previous processors
            timeout: Timeout in seconds

        Returns:
            ProcessorResult from the processor

        Raises:
            ProcessorTimeout: If processor exceeds timeout
            Exception: Other processor errors
        """
        result = None
        exception = None

        def target():
            nonlocal result, exception
            try:
                result = processor.process(file_path, context.copy())
                if not isinstance(result, ProcessorResult):
                    # Handle processors that return dict or other types
                    if isinstance(result, dict):
                        result = ProcessorResult(
                            success=result.get("success", True),
                            message=result.get("message", ""),
                            stats=result.get("stats", {}),
                            context=result.get("context", {}),
                        )
                    else:
                        result = ProcessorResult(
                            success=True,
                            message=str(result) if result else "Processed",
                            stats={},
                        )
            except Exception as e:
                exception = e

        # Run processor in thread with timeout
        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        thread.join(timeout)

        if thread.is_alive():
            # Timeout occurred
            logger.warning(f"Processor {processor.name} timed out after {timeout}s")
            raise ProcessorTimeout(
                f"Processor timed out after {timeout} seconds",
                processor.name,
                file_path,
            )

        if exception:
            raise ProcessorError(
                str(exception), processor.name, file_path
            ) from exception

        if result is None:
            raise ProcessorError("Processor returned None", processor.name, file_path)

        return result

    def process_multiple_files(
        self,
        file_paths: List[Path],
        timeout: Optional[float] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Process multiple files through the processor chain.

        Args:
            file_paths: List of files to process
            timeout: Timeout per processor per file
            progress_callback: Optional callback for progress updates (current, total)

        Returns:
            List of processing results for each file
        """
        results = []

        for i, file_path in enumerate(file_paths):
            if progress_callback:
                progress_callback(i, len(file_paths))

            try:
                result = self.process_file(file_path, timeout)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to process {file_path}: {e}")
                results.append(
                    {
                        "file_path": str(file_path),
                        "processors_run": 0,
                        "results": [],
                        "success": False,
                        "message": f"Chain execution failed: {e}",
                        "duration": 0,
                    }
                )

        if progress_callback:
            progress_callback(len(file_paths), len(file_paths))

        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        return self._stats.copy()

    def reset_stats(self) -> None:
        """Reset processing statistics."""
        self._stats = {
            "files_processed": 0,
            "total_processors_run": 0,
            "successful_processors": 0,
            "failed_processors": 0,
            "timeouts": 0,
        }

    def is_supported_file(self, file_path: Path) -> bool:
        """Check if any processor can handle the given file."""
        processors = self.plugin_manager.get_processors_for_file(file_path)
        return len(processors) > 0

    def list_processors_for_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """List all processors that would run for a given file."""
        processors = self.plugin_manager.get_processors_for_file(file_path)
        return [
            {
                "name": p.name,
                "version": p.version,
                "priority": p.priority,
                "description": p.description,
            }
            for p in processors
        ]


@contextmanager
def timeout_context(seconds: float):
    """
    Context manager for implementing timeouts using signals (Unix only).

    Note: This is a fallback for systems that support signals.
    The main timeout mechanism uses threading.
    """
    if sys.platform == "win32":
        # Windows doesn't support SIGALRM, so this is a no-op
        yield
        return

    def timeout_handler(signum, frame):
        raise TimeoutError(f"Operation timed out after {seconds} seconds")

    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(int(seconds))

    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
