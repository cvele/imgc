import logging
import os
import time
import threading
import signal
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .compressor import Compressor, human_readable_size

logger = logging.getLogger(__name__)

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.avif'}


def is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTS


class ImageHandler(FileSystemEventHandler):
    def __init__(self, compressor: Compressor, stable_seconds: float = 2.0, new_delay: float = 0.0, cooldown: float = 5.0, compress_timeout: float = 30.0):
        super().__init__()
        self.compressor = compressor
        self.stable_seconds = stable_seconds
        self.new_delay = new_delay
        self._processed = {}
        self.cooldown = cooldown
        # 0 means no per-file timeout
        self.compress_timeout = compress_timeout
        # stop event may be attached by the watcher to support responsive shutdown
        self.stop_event: Optional[threading.Event] = None

    def _should_process(self, p: Path) -> bool:
        now = time.time()
        key = str(p.resolve())
        last = self._processed.get(key)
        if last and (now - last) < self.cooldown:
            return False
        self._processed[key] = now
        return True

    def on_created(self, event):
        if event.is_directory:
            return
        p = Path(event.src_path)
        if not is_image(p):
            return
        if self.stop_event and self.stop_event.is_set():
            logger.debug('Stop requested; ignoring new event for %s', p)
            return
        if not self._should_process(p):
            logger.debug('Skipping recently processed file: %s', p)
            return
        if self.new_delay and self.new_delay > 0:
            logger.debug('Delaying new file %s for %.1fs', p, self.new_delay)
            time.sleep(self.new_delay)
        # Wait until stable, then compress
        if self.stop_event and self.stop_event.is_set():
            logger.debug('Stop requested; aborting processing of %s', p)
            return
        if not wait_for_stable_file(p, stable_seconds=self.stable_seconds):
            logger.warning('File did not stabilize: %s', p)
            return
        if self.compress_timeout and self.compress_timeout > 0:
            with ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(self.compressor.compress, p)
                try:
                    stats = fut.result(timeout=self.compress_timeout)
                except Exception as e:
                    logger.warning('Compression timed out or failed for %s: %s', p, e)
                    return
        else:
            stats = self.compressor.compress(p)

        if stats:
            if 'orig' in stats:
                logger.info('%s -> %s (saved %s, %.1f%%)', human_readable_size(stats['orig']), human_readable_size(stats['new']), human_readable_size(stats['saved']), stats['percent'])
            else:
                logger.info('Compressed -> %s', human_readable_size(stats['new']))


def wait_for_stable_file(path: Path, stable_seconds: float = 2.0, timeout: float = 30.0) -> bool:
    start = time.time()
    last_size = -1
    stable_start = None
    while True:
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            return False
        now = time.time()
        if size == last_size:
            if stable_start is None:
                stable_start = now
            elif now - stable_start >= stable_seconds:
                return True
        else:
            stable_start = None
            last_size = size
        if now - start > timeout:
            return False
        time.sleep(0.5)


def process_existing(root: Path, handler: ImageHandler):
    logger.info('Processing existing images under: %s', root)
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        for fn in filenames:
            p = Path(dirpath) / fn
            if not is_image(p):
                continue
            files.append(p)

    if not files:
        return

    workers = getattr(handler, 'workers', 1)
    file_timeout = getattr(handler, 'file_timeout', 0.0)
    stop_event = getattr(handler, 'stop_event', None)

    def _process(p: Path):
        try:
            if stop_event and stop_event.is_set():
                return
            if not handler._should_process(p):
                return
            if file_timeout and file_timeout > 0:
                if not wait_for_stable_file(p, stable_seconds=handler.stable_seconds, timeout=file_timeout):
                    logger.warning('Existing file did not stabilize: %s', p)
                    return
            # Respect per-file compress timeout
            if stop_event and stop_event.is_set():
                return
            if getattr(handler, 'compress_timeout', 0) and handler.compress_timeout > 0:
                with ThreadPoolExecutor(max_workers=1) as ex:
                    fut = ex.submit(handler.compressor.compress, p)
                    try:
                        stats = fut.result(timeout=handler.compress_timeout)
                    except Exception as e:
                        logger.warning('Compression timed out or failed for %s: %s', p, e)
                        return
            else:
                stats = handler.compressor.compress(p)

            if stats:
                if 'orig' in stats:
                    logger.info('%s -> %s (saved %s, %.1f%%)', human_readable_size(stats['orig']), human_readable_size(stats['new']), human_readable_size(stats['saved']), stats['percent'])
                else:
                    logger.info('Compressed -> %s', human_readable_size(stats['new']))
        except Exception:
            logger.exception('Error processing existing file: %s', p)

    if workers and workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {}
            for p in files:
                if stop_event and stop_event.is_set():
                    logger.info('Stop requested; aborting initial processing')
                    break
                futures[ex.submit(_process, p)] = p
            for fut in as_completed(futures):
                if stop_event and stop_event.is_set():
                    break
                # exceptions are logged inside _process
                pass
    else:
        for p in files:
            if stop_event and stop_event.is_set():
                logger.info('Stop requested; aborting initial processing')
                break
            _process(p)


def start_watch(root: Path, compressor: Compressor, workers: int = 1, file_timeout: float = 0.0, stable_seconds: float = 2.0, new_delay: float = 0.0, compress_timeout: float = 30.0):
    """Start watching `root`. This function is responsive to SIGINT/SIGTERM.

    It starts the observer immediately and runs the initial pass in a background
    thread so the main thread can respond to signals and shut down quickly.
    """
    handler = ImageHandler(compressor, stable_seconds=stable_seconds, new_delay=new_delay, compress_timeout=compress_timeout)
    handler.workers = workers
    handler.file_timeout = file_timeout

    stop_event = threading.Event()
    handler.stop_event = stop_event

    # Start the observer first so new files won't be missed while we process existing.
    observer = Observer()
    observer.schedule(handler, str(root), recursive=True)
    observer.start()

    # Run initial processing in background so main thread can handle signals promptly.
    # process_existing will consult handler.stop_event to abort early; run it in a background thread.
    bg = threading.Thread(target=process_existing, args=(root, handler), daemon=True)
    bg.start()

    def _on_signal(signum, frame):
        logger.info('Signal %s received, shutting down...', signum)
        stop_event.set()

    # Register signal handlers to set the stop event
    signal.signal(signal.SIGINT, _on_signal)
    try:
        signal.signal(signal.SIGTERM, _on_signal)
    except Exception:
        # SIGTERM may not be available on Windows; ignore if not present
        pass

    logger.info('Starting watcher on: %s', root)
    try:
        # Wait until stop_event is set. Use wait with timeout so tests that set the Event
        # (or other callers) don't have to wait the full sleep interval.
        while not stop_event.wait(0.5):
            # loop until event is set
            pass
    finally:
        # Begin shutdown
        logger.info('Stopping observer...')
        observer.stop()
        observer.join(timeout=5)
        logger.info('Waiting for background processing to finish...')
        bg.join(timeout=5)
        logger.info('Shutdown complete')
