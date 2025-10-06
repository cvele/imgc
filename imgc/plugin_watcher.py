"""
Plugin-based File Watcher for imgc.

This module provides a file system watcher that uses the plugin system
to process any file type, not just images. It replaces the hardcoded
image-only watcher with a flexible, extensible system.
"""

import logging
import os
import time
import threading
import signal
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional, Set, Dict, Any, List

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .plugin_manager import PluginManager
from .processor_chain import ProcessorChain

logger = logging.getLogger(__name__)


class PluginFileHandler(FileSystemEventHandler):
    """
    File system event handler that processes files through the plugin system.

    This handler replaces the hardcoded image processing logic with a flexible
    plugin-based approach that can handle any file type.
    """

    def __init__(
        self,
        plugin_manager: PluginManager,
        stable_seconds: float = 2.0,
        new_delay: float = 0.0,
        cooldown: float = 5.0,
        compress_timeout: float = 30.0,
        max_concurrent: int = 1,
    ):
        """
        Initialize the plugin-based file handler.

        Args:
            plugin_manager: Manager containing loaded processors
            stable_seconds: Time to wait for file stability
            new_delay: Delay before processing new files
            cooldown: Minimum time between processing the same file
            compress_timeout: Timeout per processor
            max_concurrent: Maximum concurrent file processing
        """
        super().__init__()
        self.plugin_manager = plugin_manager
        self.processor_chain = ProcessorChain(
            plugin_manager, compress_timeout, max_concurrent
        )
        self.stable_seconds = stable_seconds
        self.new_delay = new_delay
        self.cooldown = cooldown
        self._processed: Dict[str, float] = {}
        self.stop_event: Optional[threading.Event] = None

        # Get supported extensions from plugins
        self.supported_extensions = set(plugin_manager.get_supported_extensions())
        logger.info(
            f"Watching for files with extensions: {sorted(self.supported_extensions)}"
        )

    def is_supported_file(self, path: Path) -> bool:
        """Check if any plugin can handle this file type."""
        # Skip temporary files created by imgc itself
        if ".imgc.tmp" in path.name or path.name.startswith("."):
            return False

        return path.suffix.lower() in self.supported_extensions

    def _should_process(self, path: Path) -> bool:
        """Check if file should be processed based on cooldown period."""
        now = time.time()
        key = str(path.resolve())
        last = self._processed.get(key)
        if last and (now - last) < self.cooldown:
            logger.debug(
                f"Skipping {path} (cooldown: {now - last:.1f}s < {self.cooldown}s)"
            )
            return False
        self._processed[key] = now
        return True

    def on_created(self, event):
        """Handle file creation events."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        if not self.is_supported_file(file_path):
            logger.debug(f"Ignoring unsupported file: {file_path}")
            return

        if not self._should_process(file_path):
            return

        logger.info(f"New file detected: {file_path}")

        # Process in background thread to avoid blocking the watchdog
        threading.Thread(
            target=self._process_file_safely, args=(file_path,), daemon=True
        ).start()

    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        if not self.is_supported_file(file_path):
            return

        if not self._should_process(file_path):
            return

        logger.info(f"File modified: {file_path}")

        # Process in background thread
        threading.Thread(
            target=self._process_file_safely, args=(file_path,), daemon=True
        ).start()

    def _process_file_safely(self, file_path: Path):
        """Process a file with error handling and stability checking."""
        try:
            # Apply new file delay
            if self.new_delay > 0:
                logger.debug(f"Waiting {self.new_delay}s before processing {file_path}")
                time.sleep(self.new_delay)

            # Wait for file stability
            if not self._wait_for_stable_file(file_path):
                logger.warning(f"File not stable, skipping: {file_path}")
                return

            # Check if we should stop
            if self.stop_event and self.stop_event.is_set():
                logger.debug("Stop event set, skipping file processing")
                return

            # Process through plugin chain
            logger.debug(f"Processing {file_path} through plugin chain")
            result = self.processor_chain.process_file(file_path)

            if result["success"]:
                successful = result["successful_processors"]
                total = result["processors_run"]
                logger.info(
                    f"Processed {file_path}: {successful}/{total} processors succeeded"
                )

                # Log individual processor results
                for proc_result in result["results"]:
                    if proc_result["success"]:
                        logger.info(
                            f"  ✓ {proc_result['processor']}: {proc_result['result']['message']}"
                        )
                    else:
                        logger.warning(
                            f"  ✗ {proc_result['processor']}: {proc_result['result']['message']}"
                        )
            else:
                logger.error(f"Processing failed for {file_path}")

        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")

    def _wait_for_stable_file(self, file_path: Path, max_attempts: int = 10) -> bool:
        """
        Wait for file to become stable (stop changing size).

        Args:
            file_path: Path to the file
            max_attempts: Maximum number of stability checks

        Returns:
            bool: True if file is stable, False otherwise
        """
        if self.stable_seconds <= 0:
            return True

        prev_size = None

        for attempt in range(max_attempts):
            if self.stop_event and self.stop_event.is_set():
                return False

            try:
                current_size = file_path.stat().st_size

                if prev_size is not None and current_size == prev_size:
                    logger.debug(f"File stable: {file_path} ({current_size} bytes)")
                    return True

                prev_size = current_size
                logger.debug(
                    f"File size: {current_size} bytes, waiting {self.stable_seconds}s..."
                )
                time.sleep(self.stable_seconds)

            except (FileNotFoundError, OSError) as e:
                logger.debug(f"File access error (attempt {attempt + 1}): {e}")
                if attempt < max_attempts - 1:
                    time.sleep(self.stable_seconds)
                    continue
                return False

        logger.warning(
            f"File did not stabilize after {max_attempts} attempts: {file_path}"
        )
        return False


class PluginWatcher:
    """
    Plugin-based file system watcher.

    This class provides the main interface for watching directories and
    processing files through the plugin system.
    """

    def __init__(
        self,
        root_path: Path,
        plugin_dirs: Optional[List[Path]] = None,
        plugin_manager: Optional[PluginManager] = None,
        stable_seconds: float = 2.0,
        new_delay: float = 0.0,
        cooldown: float = 5.0,
        compress_timeout: float = 30.0,
        max_concurrent: int = 1,
    ):
        """
        Initialize the plugin watcher.

        Args:
            root_path: Directory to watch
            plugin_dirs: Directories to scan for plugins (ignored if plugin_manager provided)
            plugin_manager: Pre-initialized plugin manager (optional, creates new one if None)
            stable_seconds: Time to wait for file stability
            new_delay: Delay before processing new files
            cooldown: Minimum time between processing same file
            compress_timeout: Timeout per processor
            max_concurrent: Maximum concurrent processing
        """
        self.root_path = root_path.resolve()
        self.stable_seconds = stable_seconds
        self.new_delay = new_delay
        self.cooldown = cooldown
        self.compress_timeout = compress_timeout
        self.max_concurrent = max_concurrent

        # Initialize plugin system
        if plugin_manager:
            # Reuse existing plugin manager
            self.plugin_manager = plugin_manager
            logger.debug("Reusing existing plugin manager")
        else:
            # Create new plugin manager
            logger.info("Initializing plugin system...")
            self.plugin_manager = PluginManager(plugin_dirs)
            self.plugin_manager.create_plugin_directories()
            self.plugin_manager.discover_plugins()

        # Log plugin stats
        stats = self.plugin_manager.get_stats()
        logger.info(
            f"Loaded {stats['total_processors']} processors, "
            f"{stats['failed_plugins']} failed"
        )

        if stats["processors"]:
            logger.info("Available processors:")
            for proc in stats["processors"]:
                logger.info(
                    f"  - {proc['name']} v{proc['version']}: {proc['supported_extensions']}"
                )

        if not stats["processors"]:
            logger.warning(
                "No processors loaded! Files will be detected but not processed."
            )

        # Create file handler
        self.handler = PluginFileHandler(
            self.plugin_manager,
            stable_seconds,
            new_delay,
            cooldown,
            compress_timeout,
            max_concurrent,
        )

        # Setup watchdog observer
        self.observer = Observer()
        self.observer.schedule(self.handler, str(self.root_path), recursive=True)

        # Threading
        self.stop_event = threading.Event()
        self.handler.stop_event = self.stop_event

        # Signal handling
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            self.stop()

        # Setup handlers for common signals
        signals_to_handle = [signal.SIGINT, signal.SIGTERM]

        # SIGTERM is not available on Windows
        if os.name == "nt":
            signals_to_handle = [signal.SIGINT]

        for sig in signals_to_handle:
            try:
                signal.signal(sig, signal_handler)
            except (OSError, ValueError) as e:
                logger.debug(f"Could not setup signal handler for {sig}: {e}")

    def process_existing_files(self, workers: int = 1) -> Dict[str, Any]:
        """
        Process existing files in the watch directory.

        Args:
            workers: Number of worker threads for parallel processing

        Returns:
            Dict with processing statistics
        """
        logger.info(
            f"Processing existing files in {self.root_path} with {workers} workers..."
        )

        # Find all supported files
        supported_files = []
        for file_path in self.root_path.rglob("*"):
            if file_path.is_file() and self.handler.is_supported_file(file_path):
                supported_files.append(file_path)

        if not supported_files:
            logger.info("No supported files found for processing")
            return {
                "total_files": 0,
                "processed_files": 0,
                "successful_files": 0,
                "failed_files": 0,
                "duration": 0,
            }

        logger.info(f"Found {len(supported_files)} supported files to process")

        # Process files
        start_time = time.time()
        results = []

        def progress_callback(current, total):
            if current % 10 == 0 or current == total:  # Log every 10 files
                logger.info(f"Progress: {current}/{total} files processed")

        if workers == 1:
            # Single-threaded processing
            results = self.handler.processor_chain.process_multiple_files(
                supported_files, self.compress_timeout, progress_callback
            )
        else:
            # Multi-threaded processing
            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_to_file = {
                    executor.submit(
                        self.handler.processor_chain.process_file,
                        file_path,
                        self.compress_timeout,
                    ): file_path
                    for file_path in supported_files
                }

                processed = 0
                for future in as_completed(future_to_file):
                    if self.stop_event.is_set():
                        logger.info("Stop requested, cancelling remaining tasks")
                        break

                    file_path = future_to_file[future]
                    try:
                        result = future.result()
                        results.append(result)
                        processed += 1
                        progress_callback(processed, len(supported_files))
                    except Exception as e:
                        logger.error(f"Error processing {file_path}: {e}")
                        results.append(
                            {
                                "file_path": str(file_path),
                                "success": False,
                                "message": f"Processing error: {e}",
                                "processors_run": 0,
                                "duration": 0,
                            }
                        )

        # Calculate statistics
        duration = time.time() - start_time
        successful = sum(1 for r in results if r["success"])
        failed = len(results) - successful

        stats = {
            "total_files": len(supported_files),
            "processed_files": len(results),
            "successful_files": successful,
            "failed_files": failed,
            "duration": duration,
        }

        logger.info(
            f"Existing file processing complete: "
            f"{successful}/{len(results)} files processed successfully "
            f"in {duration:.1f}s"
        )

        return stats

    def start_watching(self, process_existing: bool = False, workers: int = 1):
        """
        Start watching for file changes.

        Args:
            process_existing: Whether to process existing files first
            workers: Number of workers for existing file processing
        """
        logger.info(f"Starting file watcher on {self.root_path}")

        if process_existing:
            # Process existing files BEFORE starting the watcher to avoid self-processing
            logger.info("Processing existing files before starting watcher...")
            existing_stats = self.process_existing_files(workers)
            if existing_stats["failed_files"] > 0:
                logger.warning(
                    f"{existing_stats['failed_files']} files failed during existing file processing"
                )
            logger.info("Existing file processing complete, starting file watcher...")

        # Start watching for new files (after existing file processing is complete)
        self.observer.start()
        logger.info("File watcher started. Press Ctrl+C to stop.")

        try:
            while not self.stop_event.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            self.stop()

    def stop(self):
        """Stop the file watcher."""
        logger.info("Stopping file watcher...")
        self.stop_event.set()

        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join(timeout=5.0)

        # Print final statistics
        chain_stats = self.handler.processor_chain.get_stats()
        logger.info("Final statistics:")
        logger.info(f"  Files processed: {chain_stats['files_processed']}")
        logger.info(f"  Processors run: {chain_stats['total_processors_run']}")
        logger.info(f"  Successful: {chain_stats['successful_processors']}")
        logger.info(f"  Failed: {chain_stats['failed_processors']}")
        logger.info(f"  Timeouts: {chain_stats['timeouts']}")

        logger.info("File watcher stopped")

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics."""
        plugin_stats = self.plugin_manager.get_stats()
        chain_stats = self.handler.processor_chain.get_stats()

        return {
            "watcher": {
                "root_path": str(self.root_path),
                "is_watching": self.observer.is_alive(),
                "supported_extensions": sorted(self.handler.supported_extensions),
            },
            "plugins": plugin_stats,
            "processing": chain_stats,
        }

    def reload_plugins(self):
        """Reload all plugins from disk."""
        logger.info("Reloading plugins...")
        self.plugin_manager.reload_plugins()

        # Update supported extensions
        self.handler.supported_extensions = set(
            self.plugin_manager.get_supported_extensions()
        )

        # Recreate processor chain with new plugins
        self.handler.processor_chain = ProcessorChain(
            self.plugin_manager, self.compress_timeout, self.max_concurrent
        )

        stats = self.plugin_manager.get_stats()
        logger.info(
            f"Plugins reloaded: {stats['total_processors']} processors available"
        )
