"""
Tests for the ImageProcessor plugin.

Tests the built-in image processing plugin that handles JPEG, PNG, WebP, and AVIF files.
"""

import pytest
import shutil
from pathlib import Path
from PIL import Image
from unittest.mock import patch, MagicMock
import argparse

from imgc.plugins.builtin.image_processor import ImageProcessor, human_readable_size
from imgc.plugin_api import ProcessorResult


def create_configured_processor(**config) -> ImageProcessor:
    """
    Create an ImageProcessor with custom configuration.

    This helper function mimics the plugin argument system for testing.
    """
    processor = ImageProcessor()

    # Set custom configuration values
    for key, value in config.items():
        setattr(processor, key, value)

    return processor


class TestImageProcessor:
    """Test the ImageProcessor plugin."""

    def test_plugin_properties(self):
        """Test ImageProcessor plugin properties."""
        processor = ImageProcessor()

        assert processor.name == "Image Compressor"
        assert processor.supported_extensions == [
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
            ".avif",
        ]
        assert processor.priority == 50
        assert processor.version == "1.0.0"
        assert "JPEG" in processor.description
        assert "PNG" in processor.description
        assert "WebP" in processor.description
        assert "AVIF" in processor.description

    def test_initialization_with_custom_settings(self):
        """Test ImageProcessor with custom quality settings."""
        processor = create_configured_processor(
            jpeg_quality=90, png_min=70, png_max=85, webp_quality=80, avif_quality=70
        )

        assert processor.jpeg_quality == 90
        assert processor.png_min == 70
        assert processor.png_max == 85
        assert processor.webp_quality == 80
        assert processor.avif_quality == 70

    def test_can_process_image_files(self, tmp_path):
        """Test can_process method with various file types."""
        processor = ImageProcessor()

        # Create actual image files for testing
        jpg_file = tmp_path / "image.jpg"
        png_file = tmp_path / "graphic.png"
        webp_file = tmp_path / "modern.webp"

        # Create simple test images
        img = Image.new("RGB", (10, 10), color="red")
        img.save(jpg_file, "JPEG")
        img.save(png_file, "PNG")
        img.save(webp_file, "WEBP")

        # Test supported formats with actual files
        assert processor.can_process(jpg_file)
        assert processor.can_process(png_file)
        assert processor.can_process(webp_file)

        # Test unsupported formats
        pdf_file = tmp_path / "document.pdf"
        pdf_file.write_bytes(b"fake PDF")
        assert not processor.can_process(pdf_file)

        # Test non-existent files
        assert not processor.can_process(Path("non-existent.jpg"))

    def test_process_jpeg_compression(self, tmp_path):
        """Test JPEG compression processing."""
        # Create test JPEG
        test_file = tmp_path / "test.jpg"
        img = Image.new("RGB", (200, 200), color="red")
        img.save(test_file, "JPEG", quality=95)  # High quality

        original_size = test_file.stat().st_size

        # Process with lower quality
        processor = create_configured_processor(jpeg_quality=50)
        result = processor.process(test_file, {})

        assert isinstance(result, ProcessorResult)
        assert result.success is True
        assert "Compressed JPG image" in result.message
        assert result.stats["original_size"] == original_size
        assert result.stats["new_size"] < original_size  # Should be smaller
        assert result.stats["bytes_saved"] > 0
        assert result.stats["percent_change"] > 0
        assert result.stats["format"] == "JPG"
        assert result.context["compressed"] is True
        assert result.context["format"] == ".jpg"

    def test_process_jpeg_with_alpha(self, tmp_path):
        """Test JPEG processing with alpha channel (should convert to RGB)."""
        # Create RGBA PNG first, then rename to .jpg to test alpha handling
        test_file = tmp_path / "alpha.png"
        img = Image.new("RGBA", (100, 100), (255, 0, 0, 128))  # Red with transparency
        img.save(test_file, "PNG")

        # Rename to .jpg to test alpha handling in JPEG processing
        jpeg_file = test_file.with_suffix(".jpg")
        test_file.rename(jpeg_file)

        processor = ImageProcessor()
        result = processor.process(jpeg_file, {})

        assert result.success is True
        assert "JPG" in result.message
        assert result.stats["format"] == "JPG"

    def test_process_png_without_pngquant(self, tmp_path, monkeypatch):
        """Test PNG processing without pngquant (PIL fallback)."""
        # Mock shutil.which to return None (pngquant not found)
        monkeypatch.setattr(shutil, "which", lambda cmd: None)

        # Create test PNG
        test_file = tmp_path / "test.png"
        img = Image.new("RGB", (100, 100), color="blue")
        img.save(test_file, "PNG")

        processor = ImageProcessor()
        result = processor.process(test_file, {})

        assert result.success is True
        assert "PNG" in result.message
        assert result.stats["format"] == "PNG"

    def test_process_png_with_pngquant(self, tmp_path, monkeypatch):
        """Test PNG processing with pngquant."""
        # Create test PNG
        test_file = tmp_path / "test.png"
        img = Image.new("RGB", (100, 100), color="green")
        img.save(test_file, "PNG")

        # Mock pngquant to simulate success
        def mock_run_pngquant(self, src, tmp):
            # Copy file to simulate pngquant output
            shutil.copy2(src, tmp)
            return True

        monkeypatch.setattr(ImageProcessor, "_run_pngquant", mock_run_pngquant)

        processor = ImageProcessor()
        result = processor.process(test_file, {})

        assert result.success is True
        assert "PNG" in result.message

    def test_process_webp(self, tmp_path):
        """Test WebP processing."""
        # Create test WebP
        test_file = tmp_path / "test.webp"
        img = Image.new("RGB", (100, 100), color="yellow")
        img.save(test_file, "WEBP", quality=95)  # High quality

        original_size = test_file.stat().st_size

        # Process with lower quality
        processor = create_configured_processor(webp_quality=60)
        result = processor.process(test_file, {})

        assert result.success is True
        assert "WEBP" in result.message
        assert result.stats["original_size"] == original_size
        assert result.stats["format"] == "WEBP"

    def test_process_avif_success(self, tmp_path):
        """Test AVIF processing when imageio is available."""
        # Create test image and save as AVIF
        test_file = tmp_path / "test.avif"
        img = Image.new("RGB", (50, 50), color="purple")
        img.save(
            test_file, "PNG"
        )  # Save as PNG first, then rename to test AVIF processing

        # Rename to AVIF
        avif_file = test_file.with_suffix(".avif")
        test_file.rename(avif_file)

        processor = ImageProcessor()
        result = processor.process(avif_file, {})

        # Result depends on whether imageio is available
        if result.success:
            assert "AVIF" in result.message
            assert result.stats["format"] == "AVIF"
        else:
            # If imageio not available, should fail gracefully
            assert "imageio" in result.message or "AVIF" in result.message

    def test_process_avif_imageio_missing(self, tmp_path, monkeypatch):
        """Test AVIF processing when imageio is not available."""

        # Mock the _process_avif method to simulate ImportError
        def mock_process_avif(self, src, tmp):
            raise ImportError("No module named 'imageio'")

        monkeypatch.setattr(ImageProcessor, "_process_avif", mock_process_avif)

        # Create test file
        test_file = tmp_path / "test.avif"
        img = Image.new("RGB", (50, 50), color="orange")
        img.save(test_file, "PNG")

        processor = ImageProcessor()
        result = processor.process(test_file, {})

        assert result.success is False
        assert "imageio" in result.message.lower()

    def test_process_unsupported_format(self, tmp_path):
        """Test processing unsupported file format."""
        # Create non-image file
        test_file = tmp_path / "document.pdf"
        test_file.write_bytes(b"fake PDF content")

        processor = ImageProcessor()
        result = processor.process(test_file, {})

        assert result.success is False
        assert "Unsupported image format" in result.message

    def test_process_invalid_file(self):
        """Test processing non-existent file."""
        processor = ImageProcessor()
        result = processor.process(Path("/non/existent/file.jpg"), {})

        assert result.success is False
        assert "Invalid or inaccessible file" in result.message

    def test_process_corrupted_image(self, tmp_path):
        """Test processing corrupted image file."""
        # Create file with image extension but invalid content
        test_file = tmp_path / "corrupted.jpg"
        test_file.write_bytes(b"This is not a valid JPEG file")

        processor = ImageProcessor()
        result = processor.process(test_file, {})

        assert result.success is False  # Should fail on corrupted image

    def test_enhanced_can_process(self, tmp_path):
        """Test the enhanced can_process method."""
        processor = ImageProcessor()

        # Create valid image file
        valid_file = tmp_path / "valid.jpg"
        img = Image.new("RGB", (50, 50), color="blue")
        img.save(valid_file, "JPEG")

        # Create empty file
        empty_file = tmp_path / "empty.jpg"
        empty_file.write_bytes(b"")

        # Test validation
        assert processor.can_process(valid_file)
        assert not processor.can_process(empty_file)  # Empty file should be rejected
        assert not processor.can_process(Path("/non/existent.jpg"))  # Non-existent file


class TestImageProcessorFormats:
    """Test ImageProcessor with different image formats."""

    def test_jpeg_formats(self, tmp_path):
        """Test both .jpg and .jpeg extensions."""
        processor = ImageProcessor()

        for ext in [".jpg", ".jpeg"]:
            test_file = tmp_path / f"test{ext}"
            img = Image.new("RGB", (50, 50), color="red")
            img.save(test_file, "JPEG")

            result = processor.process(test_file, {})
            assert result.success is True
            assert result.stats["format"] in [
                "JPG",
                "JPEG",
            ]  # Either format name is acceptable

    def test_png_optimization(self, tmp_path):
        """Test PNG optimization."""
        test_file = tmp_path / "test.png"
        img = Image.new("RGB", (100, 100), color="green")
        img.save(test_file, "PNG")

        processor = create_configured_processor(png_min=50, png_max=70)
        result = processor.process(test_file, {})

        assert result.success is True
        assert result.stats["format"] == "PNG"

    def test_webp_quality_settings(self, tmp_path):
        """Test WebP with different quality settings."""
        test_file = tmp_path / "test.webp"
        img = Image.new("RGB", (100, 100), color="cyan")
        img.save(test_file, "WEBP", quality=95)

        # Test with lower quality
        processor = create_configured_processor(webp_quality=40)
        result = processor.process(test_file, {})

        assert result.success is True
        assert result.stats["format"] == "WEBP"

    def test_plugin_arguments_declaration(self):
        """Test that ImageProcessor declares the correct plugin arguments."""
        processor = ImageProcessor()
        args = processor.get_plugin_arguments()

        # Should have 5 quality arguments
        assert len(args) == 5

        arg_names = [arg.name for arg in args]
        assert "jpeg_quality" in arg_names
        assert "png_min" in arg_names
        assert "png_max" in arg_names
        assert "webp_quality" in arg_names
        assert "avif_quality" in arg_names

        # Check types and defaults
        for arg in args:
            assert arg.type == int
            assert isinstance(arg.default, int)
            assert arg.help != ""

    def test_plugin_namespace(self):
        """Test that ImageProcessor uses the correct namespace."""
        processor = ImageProcessor()
        assert processor.get_plugin_namespace() == "image"

    def test_configure_from_args(self):
        """Test configuring ImageProcessor from parsed arguments."""
        processor = ImageProcessor()

        # Create mock args namespace
        args = argparse.Namespace()
        args.image_jpeg_quality = 95
        args.image_png_min = 70
        args.image_png_max = 85
        args.image_webp_quality = 75
        args.image_avif_quality = 55

        # Configure processor
        processor.configure_from_args(args)

        # Check that values were set
        assert processor.jpeg_quality == 95
        assert processor.png_min == 70
        assert processor.png_max == 85
        assert processor.webp_quality == 75
        assert processor.avif_quality == 55


class TestHumanReadableSize:
    """Test the human_readable_size utility function."""

    def test_bytes(self):
        """Test formatting bytes."""
        assert human_readable_size(0) == "0.0B"
        assert human_readable_size(512) == "512.0B"
        assert human_readable_size(1023) == "1023.0B"

    def test_kilobytes(self):
        """Test formatting kilobytes."""
        assert human_readable_size(1024) == "1.0KB"
        assert human_readable_size(1536) == "1.5KB"
        assert human_readable_size(1024 * 1023) == "1023.0KB"

    def test_megabytes(self):
        """Test formatting megabytes."""
        assert human_readable_size(1024 * 1024) == "1.0MB"
        assert human_readable_size(int(1024 * 1024 * 2.5)) == "2.5MB"

    def test_gigabytes(self):
        """Test formatting gigabytes."""
        assert human_readable_size(1024 * 1024 * 1024) == "1.0GB"
        assert human_readable_size(int(1024 * 1024 * 1024 * 1.5)) == "1.5GB"

    def test_terabytes(self):
        """Test formatting terabytes."""
        assert human_readable_size(1024 * 1024 * 1024 * 1024) == "1.0TB"

    def test_large_sizes(self):
        """Test very large file sizes."""
        petabyte = 1024 * 1024 * 1024 * 1024 * 1024
        assert human_readable_size(petabyte) == "1.0PB"
