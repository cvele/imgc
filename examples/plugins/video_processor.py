"""
Example Video Processor Plugin for imgc.

This plugin demonstrates how to create processors for video files using external tools.
It shows integration with ffmpeg for video compression and analysis.

REQUIREMENTS:
- ffmpeg must be installed and available in PATH
- This is just an example - adapt for your specific needs

To use this plugin:
1. Install ffmpeg: https://ffmpeg.org/download.html
2. Copy this file to ~/.imgc/plugins/
3. Restart imgc
4. Video files will be automatically processed

Author: Example User
Version: 1.0.0
"""

import sys
import subprocess
import shutil
import json
from pathlib import Path

# Standard imgc plugin imports
try:
    from imgc.plugin_api import FileProcessor, ProcessorResult
except ImportError:
    # Fallback for standalone testing
    imgc_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(imgc_root))
    from imgc.plugin_api import FileProcessor, ProcessorResult


class VideoProcessor(FileProcessor):
    """
    Video file processor using ffmpeg.

    This processor can:
    - Analyze video files (duration, resolution, bitrate)
    - Compress videos to reduce file size
    - Convert between formats
    - Extract metadata
    """

    def __init__(self, target_quality: str = "28", max_width: int = 1920):
        """
        Initialize video processor.

        Args:
            target_quality: CRF value for h264 (18-28 is good range)
            max_width: Maximum width to scale videos to
        """
        self.target_quality = target_quality
        self.max_width = max_width

    @property
    def name(self):
        return "Video Compressor"

    @property
    def supported_extensions(self):
        return [".mp4", ".avi", ".mov", ".mkv", ".flv", ".webm", ".m4v"]

    @property
    def priority(self):
        return 75  # Medium-low priority (videos take time to process)

    @property
    def version(self):
        return "1.0.0"

    @property
    def description(self):
        return "Compresses and analyzes video files using ffmpeg"

    def can_process(self, file_path):
        """Check if we can process this video file."""
        if not super().can_process(file_path):
            return False

        # Check if ffmpeg is available
        if not shutil.which("ffmpeg"):
            return False

        # Check file size (skip very large files for safety)
        try:
            file_size = file_path.stat().st_size
            # Skip files larger than 1GB for this example
            if file_size > 1024 * 1024 * 1024:
                return False
        except:
            return False

        return True

    def process(self, file_path, context):
        """
        Process a video file.

        This example compresses the video and extracts metadata.
        """
        try:
            # First, analyze the video
            metadata = self._get_video_metadata(file_path)
            if not metadata:
                return ProcessorResult(
                    success=False, message="Could not analyze video file"
                )

            original_size = file_path.stat().st_size

            # Create temporary output file
            output_path = file_path.with_suffix(".compressed" + file_path.suffix)

            # Compress the video
            success = self._compress_video(file_path, output_path, metadata)

            if not success:
                # Clean up
                if output_path.exists():
                    output_path.unlink()
                return ProcessorResult(
                    success=False, message="Video compression failed"
                )

            # Replace original with compressed version
            compressed_size = output_path.stat().st_size

            # Only replace if we actually saved space
            if compressed_size < original_size:
                output_path.replace(file_path)
                saved_bytes = original_size - compressed_size
                percent_saved = (saved_bytes / original_size) * 100

                stats = {
                    "original_size": original_size,
                    "compressed_size": compressed_size,
                    "bytes_saved": saved_bytes,
                    "percent_saved": round(percent_saved, 1),
                    "duration": metadata.get("duration", 0),
                    "original_bitrate": metadata.get("bitrate", 0),
                    "resolution": f"{metadata.get('width', 0)}x{metadata.get('height', 0)}",
                }

                message = (
                    f"Compressed video: {self._format_size(original_size)} → "
                    f"{self._format_size(compressed_size)} ({percent_saved:.1f}% saved)"
                )
            else:
                # Compression didn't help, keep original
                output_path.unlink()
                stats = metadata
                message = "Video already optimally compressed, no changes made"

            return ProcessorResult(
                success=True,
                message=message,
                stats=stats,
                context={"video_processed": True, "format": file_path.suffix},
            )

        except Exception as e:
            return ProcessorResult(
                success=False, message=f"Video processing error: {e}"
            )

    def _get_video_metadata(self, file_path):
        """Extract metadata from video file using ffprobe."""
        try:
            cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(file_path),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                return None

            data = json.loads(result.stdout)

            # Extract relevant information
            format_info = data.get("format", {})
            video_stream = None

            # Find video stream
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    video_stream = stream
                    break

            if not video_stream:
                return None

            metadata = {
                "duration": float(format_info.get("duration", 0)),
                "bitrate": int(format_info.get("bit_rate", 0)),
                "width": int(video_stream.get("width", 0)),
                "height": int(video_stream.get("height", 0)),
                "codec": video_stream.get("codec_name", "unknown"),
                "fps": eval(
                    video_stream.get("r_frame_rate", "0/1")
                ),  # Convert fraction to float
            }

            return metadata

        except Exception:
            return None

    def _compress_video(self, input_path, output_path, metadata):
        """Compress video using ffmpeg."""
        try:
            # Build ffmpeg command
            cmd = [
                "ffmpeg",
                "-i",
                str(input_path),
                "-c:v",
                "libx264",  # Use h264 codec
                "-crf",
                str(self.target_quality),  # Quality setting
                "-preset",
                "medium",  # Encoding speed/compression tradeoff
                "-c:a",
                "aac",  # Audio codec
                "-b:a",
                "128k",  # Audio bitrate
                "-movflags",
                "+faststart",  # Optimize for streaming
                "-y",  # Overwrite output file
            ]

            # Scale down if video is too large
            width = metadata.get("width", 0)
            if width > self.max_width:
                cmd.extend(["-vf", f"scale={self.max_width}:-2"])

            cmd.append(str(output_path))

            # Run compression with timeout
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300  # 5 minute timeout
            )

            return result.returncode == 0

        except subprocess.TimeoutExpired:
            return False
        except Exception:
            return False

    def _format_size(self, size_bytes):
        """Format file size in human readable format."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f}TB"


class VideoAnalyzer(FileProcessor):
    """
    Video analyzer that only extracts metadata without compression.

    This is useful when you want to analyze videos without modifying them.
    """

    @property
    def name(self):
        return "Video Analyzer"

    @property
    def supported_extensions(self):
        return [".mp4", ".avi", ".mov", ".mkv", ".flv", ".webm", ".m4v"]

    @property
    def priority(self):
        return 50  # Higher priority than compressor

    @property
    def description(self):
        return "Analyzes video files and extracts metadata without modification"

    def can_process(self, file_path):
        """Only process if ffprobe is available."""
        if not super().can_process(file_path):
            return False
        return shutil.which("ffprobe") is not None

    def process(self, file_path, context):
        """Analyze video without modification."""
        try:
            # Reuse the metadata extraction from VideoProcessor
            processor = VideoProcessor()
            metadata = processor._get_video_metadata(file_path)

            if not metadata:
                return ProcessorResult(
                    success=False, message="Could not analyze video metadata"
                )

            # Add file size to metadata
            metadata["file_size"] = file_path.stat().st_size

            duration_str = f"{metadata['duration']:.1f}s"
            resolution_str = f"{metadata['width']}x{metadata['height']}"

            message = (
                f"Video analysis: {duration_str}, {resolution_str}, "
                f"{metadata['codec']} codec"
            )

            return ProcessorResult(
                success=True,
                message=message,
                stats=metadata,
                context={"video_analyzed": True, "duration": metadata["duration"]},
            )

        except Exception as e:
            return ProcessorResult(success=False, message=f"Video analysis failed: {e}")


# Standalone testing
if __name__ == "__main__":
    processor = VideoProcessor()
    print(f"Plugin: {processor.name} v{processor.version}")
    print(f"Supports: {processor.supported_extensions}")
    print(f"ffmpeg available: {shutil.which('ffmpeg') is not None}")
    print(f"ffprobe available: {shutil.which('ffprobe') is not None}")

    analyzer = VideoAnalyzer()
    print(f"\\nAnalyzer: {analyzer.name}")
    print(f"Can analyze: {analyzer.can_process(Path('test.mp4'))}")
