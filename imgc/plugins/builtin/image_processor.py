"""
Built-in Image Processor Plugin for imgc.

This plugin handles compression of JPEG, PNG, WebP, and AVIF image files.
It migrates the functionality from the original hardcoded compressor.py.
"""

import shutil
import subprocess
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List

# Add the imgc package to Python path for imports
imgc_path = Path(__file__).parent.parent.parent
if str(imgc_path) not in sys.path:
    sys.path.insert(0, str(imgc_path.parent))

from imgc.plugin_api import FileProcessor, ProcessorResult, PluginArgument


def human_readable_size(n: int) -> str:
    """
    Format file size in human readable format.

    Args:
        n: Size in bytes

    Returns:
        Human readable size string (e.g., "1.5MB", "256KB")
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024.0:
            return f"{n:.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}PB"


logger = logging.getLogger(__name__)

# Suppress verbose PIL plugin loading messages
pil_logger = logging.getLogger("PIL")
pil_logger.setLevel(logging.WARNING)


class ImageProcessor(FileProcessor):
    """
    Comprehensive image compression processor.

    Handles JPEG, PNG, WebP, and AVIF formats with configurable quality settings
    and optimized compression strategies for each format.
    """

    def __init__(self):
        """
        Initialize the image processor with default quality settings.

        Quality settings can be configured via command-line arguments or environment variables.
        """
        # Set default values (will be overridden by configure_from_args)
        self.jpeg_quality = 85
        self.png_min = 65
        self.png_max = 80
        self.webp_quality = 85
        self.avif_quality = 65

    @property
    def name(self) -> str:
        return "Image Compressor"

    @property
    def supported_extensions(self) -> List[str]:
        return [".jpg", ".jpeg", ".png", ".webp", ".avif"]

    @property
    def priority(self) -> int:
        return 50  # Medium priority - runs after validators but before converters

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Compresses JPEG, PNG, WebP, and AVIF images with optimized settings"

    def get_plugin_arguments(self) -> List[PluginArgument]:
        """Define command-line arguments for image compression quality settings."""
        return [
            PluginArgument(
                "jpeg_quality",
                int,
                85,
                "JPEG compression quality (1-100, higher = better quality, larger files)",
            ),
            PluginArgument(
                "png_min",
                int,
                65,
                "PNG minimum compression level (0-100, lower = better compression)",
            ),
            PluginArgument(
                "png_max",
                int,
                80,
                "PNG maximum compression level (0-100, must be >= png-min)",
            ),
            PluginArgument(
                "webp_quality",
                int,
                85,
                "WebP compression quality (1-100, higher = better quality, larger files)",
            ),
            PluginArgument(
                "avif_quality",
                int,
                65,
                "AVIF compression quality (1-100, higher = better quality, larger files)",
            ),
        ]

    def get_plugin_namespace(self) -> str:
        """Use 'image' as the namespace for cleaner CLI arguments."""
        return "image"

    def process(self, file_path: Path, context: Dict[str, Any]) -> ProcessorResult:
        """
        Process an image file with format-specific compression.

        Args:
            file_path: Path to the image file
            context: Processing context from previous processors

        Returns:
            ProcessorResult with compression statistics
        """
        if not self.validate_file(file_path):
            return ProcessorResult(
                success=False, message=f"Invalid or inaccessible file: {file_path}"
            )

        try:
            # Get original file size
            original_size = file_path.stat().st_size

            # Create temporary file for processing
            tmp_suffix = ".imgc.tmp"
            tmp_path = file_path.with_suffix(file_path.suffix + tmp_suffix)

            # Process based on file extension
            extension = file_path.suffix.lower()

            if extension in (".jpg", ".jpeg"):
                success = self._process_jpeg(file_path, tmp_path)
            elif extension == ".png":
                success = self._process_png(file_path, tmp_path)
            elif extension == ".webp":
                success = self._process_webp(file_path, tmp_path)
            elif extension == ".avif":
                success = self._process_avif(file_path, tmp_path)
            else:
                return ProcessorResult(
                    success=False, message=f"Unsupported image format: {extension}"
                )

            if not success:
                # Clean up temp file if it exists
                if tmp_path.exists():
                    tmp_path.unlink()
                return ProcessorResult(
                    success=False, message=f"Failed to process {extension} image"
                )

            # Replace original with compressed version
            tmp_path.replace(file_path)

            # Calculate compression statistics
            new_size = file_path.stat().st_size
            saved = original_size - new_size
            percent_change = ((saved / original_size) * 100) if original_size > 0 else 0

            stats = {
                "original_size": original_size,
                "new_size": new_size,
                "bytes_saved": saved,
                "percent_change": percent_change,
                "format": extension.upper().lstrip("."),
            }

            message = (
                f"Compressed {extension.upper().lstrip('.')} image: "
                f"{human_readable_size(original_size)} → {human_readable_size(new_size)} "
                f"({percent_change:+.1f}%)"
            )

            logger.info(message)

            return ProcessorResult(
                success=True,
                message=message,
                stats=stats,
                context={"compressed": True, "format": extension},
            )

        except Exception as e:
            logger.error(f"Image processing failed for {file_path}: {e}")
            return ProcessorResult(
                success=False, message=f"Image processing error: {e}"
            )

    def _process_jpeg(self, src: Path, tmp: Path) -> bool:
        """Process JPEG image with quality-based compression."""
        try:
            from PIL import Image

            with Image.open(src) as img:
                # Handle transparency by converting to RGB with white background
                if img.mode in ("RGBA", "LA"):
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "RGBA":
                        background.paste(img, mask=img.split()[-1])
                    else:  # LA
                        background.paste(img, mask=img.split()[-1])
                    img = background

                img.save(tmp, format="JPEG", quality=self.jpeg_quality, optimize=True)

            return True

        except Exception as e:
            logger.warning(f"JPEG processing failed: {e}")
            return False

    def _process_png(self, src: Path, tmp: Path) -> bool:
        """Process PNG image with pngquant fallback to PIL optimization."""
        # Try pngquant first for better compression
        if self._run_pngquant(src, tmp):
            return True

        # Fallback to PIL optimization
        try:
            from PIL import Image

            with Image.open(src) as img:
                img.save(tmp, format="PNG", optimize=True)

            return True

        except Exception as e:
            logger.warning(f"PNG processing failed: {e}")
            return False

    def _run_pngquant(self, src: Path, tmp: Path) -> bool:
        """Run pngquant external tool for PNG optimization."""
        pngquant = shutil.which("pngquant")
        if not pngquant:
            logger.debug("pngquant not found, using PIL fallback")
            return False

        cmd = [
            pngquant,
            "--quality",
            f"{self.png_min}-{self.png_max}",
            "--output",
            str(tmp),
            "--force",
            str(src),
        ]

        try:
            result = subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,  # 30 second timeout
            )
            logger.debug(f"pngquant completed successfully")
            return True

        except subprocess.CalledProcessError as e:
            logger.debug(f"pngquant failed (exit {e.returncode}), using PIL fallback")
            return False
        except subprocess.TimeoutExpired:
            logger.warning("pngquant timed out, using PIL fallback")
            return False
        except Exception as e:
            logger.debug(f"pngquant error: {e}, using PIL fallback")
            return False

    def _process_webp(self, src: Path, tmp: Path) -> bool:
        """Process WebP image with quality-based compression."""
        try:
            from PIL import Image

            with Image.open(src) as img:
                img.save(tmp, format="WEBP", quality=self.webp_quality, optimize=True)

            return True

        except Exception as e:
            logger.warning(f"WebP processing failed: {e}")
            return False

    def _process_avif(self, src: Path, tmp: Path) -> bool:
        """Process AVIF image using imageio v3 API."""
        try:
            import imageio.v3 as iio
            from PIL import Image

            with Image.open(src) as img:
                arr = img.convert("RGB")
                # Note: AVIF quality parameter not supported in current imageio version
                # Uses default compression settings
                iio.imwrite(str(tmp), arr, extension=".avif")

            return True

        except ImportError:
            logger.warning("imageio not installed; AVIF compression skipped")
            return False
        except Exception as e:
            logger.warning(f"AVIF processing failed: {e}")
            return False

    def can_process(self, file_path: Path) -> bool:
        """
        Enhanced file type detection for images.

        Checks both extension and basic file validation.
        """
        if not super().can_process(file_path):
            return False

        # Additional validation for image files
        return self.validate_file(file_path) and file_path.stat().st_size > 0
