"""
Integration tests for imgc with real image files.

These tests use actual image files to test the complete compression workflow,
including different formats, file watcher integration, and end-to-end scenarios.
"""

import os
import shutil
import tempfile
import threading
import time
from pathlib import Path
from typing import Dict, Any, List
import pytest
from PIL import Image, ImageDraw, ImageFont

from imgc.compressor import Compressor
from imgc.watcher import ImageHandler, process_existing


class TestImageFactory:
    """Factory for creating test images in various formats and sizes."""
    
    @staticmethod
    def create_jpeg(path: Path, size: tuple = (800, 600), quality: int = 95, 
                   color: tuple = (255, 128, 64)) -> Dict[str, Any]:
        """Create a JPEG test image with specified parameters."""
        img = Image.new('RGB', size, color)
        
        # Add some detail to make compression more realistic
        draw = ImageDraw.Draw(img)
        for i in range(0, size[0], 50):
            draw.line([(i, 0), (i, size[1])], fill=(255, 255, 255), width=2)
        for i in range(0, size[1], 50):
            draw.line([(0, i), (size[0], i)], fill=(255, 255, 255), width=2)
        
        # Add some text
        try:
            # Try to use a default font, fall back to basic if not available
            font = ImageFont.load_default()
            draw.text((50, 50), f"Test Image {size[0]}x{size[1]}", 
                     fill=(255, 255, 255), font=font)
        except:
            draw.text((50, 50), f"Test Image {size[0]}x{size[1]}", 
                     fill=(255, 255, 255))
        
        img.save(path, format='JPEG', quality=quality)
        return {
            'path': path,
            'format': 'JPEG',
            'size': size,
            'quality': quality,
            'file_size': path.stat().st_size
        }
    
    @staticmethod
    def create_png(path: Path, size: tuple = (800, 600), 
                  color: tuple = (255, 128, 64, 255)) -> Dict[str, Any]:
        """Create a PNG test image with transparency."""
        img = Image.new('RGBA', size, color)
        
        # Add some transparency effects
        draw = ImageDraw.Draw(img)
        for i in range(10):
            alpha = 255 - (i * 25)
            circle_color = (*color[:3], alpha)
            draw.ellipse([
                (50 + i * 30, 50 + i * 20),
                (150 + i * 30, 150 + i * 20)
            ], fill=circle_color)
        
        img.save(path, format='PNG')
        return {
            'path': path,
            'format': 'PNG',
            'size': size,
            'file_size': path.stat().st_size
        }
    
    @staticmethod
    def create_webp(path: Path, size: tuple = (800, 600), quality: int = 85,
                   color: tuple = (64, 128, 255)) -> Dict[str, Any]:
        """Create a WebP test image."""
        img = Image.new('RGB', size, color)
        
        # Add gradient effect
        draw = ImageDraw.Draw(img)
        for y in range(size[1]):
            gradient_color = (
                int(color[0] * (1 - y / size[1])),
                int(color[1] * (1 - y / size[1])),
                int(color[2] * (1 - y / size[1]))
            )
            draw.line([(0, y), (size[0], y)], fill=gradient_color)
        
        img.save(path, format='WEBP', quality=quality)
        return {
            'path': path,
            'format': 'WEBP',
            'size': size,
            'quality': quality,
            'file_size': path.stat().st_size
        }


@pytest.fixture
def test_images_dir(tmp_path):
    """Create a directory with various test images."""
    images_dir = tmp_path / "test_images"
    images_dir.mkdir()
    
    factory = TestImageFactory()
    
    # Create images of different formats and sizes
    images = {
        'large_jpeg': factory.create_jpeg(
            images_dir / "large_photo.jpg", 
            size=(1920, 1080), 
            quality=95
        ),
        'medium_jpeg': factory.create_jpeg(
            images_dir / "medium_photo.jpg", 
            size=(800, 600), 
            quality=90
        ),
        'small_jpeg': factory.create_jpeg(
            images_dir / "small_photo.jpg", 
            size=(400, 300), 
            quality=85
        ),
        'png_with_alpha': factory.create_png(
            images_dir / "transparent.png", 
            size=(600, 400)
        ),
        'webp_image': factory.create_webp(
            images_dir / "modern.webp", 
            size=(800, 600), 
            quality=80
        )
    }
    
    return images_dir, images


class TestImageCompression:
    """Test image compression with real images."""
    
    def test_compress_various_formats(self, test_images_dir):
        """Test compression of different image formats."""
        images_dir, images = test_images_dir
        compressor = Compressor(jpeg_quality=70, webp_quality=75)
        
        results = {}
        for name, image_info in images.items():
            path = image_info['path']
            original_size = path.stat().st_size
            
            stats = compressor.compress(path)
            
            assert stats is not None, f"Compression failed for {name}"
            assert 'orig' in stats, f"Missing original size for {name}"
            assert 'new' in stats, f"Missing new size for {name}"
            assert stats['orig'] == original_size, f"Original size mismatch for {name}"
            
            # For lossy formats, we expect some compression
            if image_info['format'] in ['JPEG', 'WEBP']:
                assert stats['new'] < stats['orig'], f"No compression achieved for {name}"
                compression_ratio = stats['new'] / stats['orig']
                assert compression_ratio < 0.95, f"Insufficient compression for {name}: {compression_ratio}"
            
            results[name] = stats
        
        # Verify all images still exist and are valid
        for name, image_info in images.items():
            path = image_info['path']
            assert path.exists(), f"Image {name} was deleted during compression"
            
            # Verify image can still be opened
            with Image.open(path) as img:
                assert img.size == image_info['size'], f"Image dimensions changed for {name}"
    
    def test_compression_preserves_metadata(self, test_images_dir):
        """Test that compression preserves essential image properties."""
        images_dir, images = test_images_dir
        compressor = Compressor(jpeg_quality=80)
        
        # Test with JPEG image
        jpeg_path = images['medium_jpeg']['path']
        
        # Get original properties without keeping file open
        with Image.open(jpeg_path) as original_image:
            original_size = original_image.size
            original_mode = original_image.mode
        
        # Compress the image
        stats = compressor.compress(jpeg_path)
        assert stats is not None
        
        # Verify image properties are preserved
        with Image.open(jpeg_path) as compressed_image:
            assert compressed_image.size == original_size
            assert compressed_image.mode == original_mode
    
    def test_compression_with_different_qualities(self, test_images_dir):
        """Test compression with different quality settings."""
        images_dir, images = test_images_dir
        
        # Create copies for different quality tests
        original_path = images['medium_jpeg']['path']
        test_files = []
        
        for quality in [50, 70, 90]:
            copy_path = images_dir / f"quality_test_{quality}.jpg"
            shutil.copy2(original_path, copy_path)
            test_files.append((copy_path, quality))
        
        results = []
        for path, quality in test_files:
            compressor = Compressor(jpeg_quality=quality)
            stats = compressor.compress(path)
            assert stats is not None
            results.append((quality, stats['new']))
        
        # Higher quality should result in larger file sizes
        results.sort(key=lambda x: x[0])  # Sort by quality
        for i in range(1, len(results)):
            prev_quality, prev_size = results[i-1]
            curr_quality, curr_size = results[i]
            # Allow some tolerance as compression can be non-linear
            assert curr_size >= prev_size * 0.8, \
                f"Quality {curr_quality} resulted in smaller file than quality {prev_quality}"


class TestWatcherIntegration:
    """Test file watcher integration with real images."""
    
    def test_watcher_processes_new_images(self, test_images_dir):
        """Test that watcher processes newly created images."""
        images_dir, _ = test_images_dir
        watch_dir = images_dir / "watched"
        watch_dir.mkdir()
        
        # Track compression calls
        compressed_files = []
        
        class MockCompressor:
            def compress(self, path: Path):
                compressed_files.append(path.name)
                # Simulate compression by slightly reducing file size
                original_size = path.stat().st_size
                return {
                    'orig': original_size,
                    'new': int(original_size * 0.8),
                    'saved': int(original_size * 0.2)
                }
        
        handler = ImageHandler(
            compressor=MockCompressor(),
            stable_seconds=0.1,
            new_delay=0.1,
            cooldown=0.5,
            compress_timeout=5.0
        )
        handler.workers = 1
        
        # Create some images in the watched directory
        factory = TestImageFactory()
        
        # Create images with small delay to simulate real file creation
        new_images = [
            factory.create_jpeg(watch_dir / "new1.jpg", size=(400, 300)),
            factory.create_png(watch_dir / "new2.png", size=(300, 200)),
            factory.create_webp(watch_dir / "new3.webp", size=(500, 400))
        ]
        
        # Process existing files (simulates watcher startup)
        process_existing(watch_dir, handler)
        
        # Wait for processing to complete
        time.sleep(0.5)
        
        # Verify all images were processed
        expected_files = {"new1.jpg", "new2.png", "new3.webp"}
        assert set(compressed_files) == expected_files
    
    def test_watcher_respects_cooldown(self, test_images_dir):
        """Test that watcher respects cooldown period."""
        images_dir, _ = test_images_dir
        
        compression_count = {'count': 0}
        
        class CountingCompressor:
            def compress(self, path: Path):
                compression_count['count'] += 1
                return {'orig': 1000, 'new': 800, 'saved': 200}
        
        handler = ImageHandler(
            compressor=CountingCompressor(),
            stable_seconds=0.01,
            new_delay=0,
            cooldown=1.0,  # 1 second cooldown
            compress_timeout=5.0
        )
        
        # Create a test image
        test_path = images_dir / "cooldown_test.jpg"
        TestImageFactory.create_jpeg(test_path, size=(200, 200))
        
        # First call should process (and record timestamp)
        assert handler._should_process(test_path) is True
        
        # Immediate second call should be blocked by cooldown
        assert handler._should_process(test_path) is False
        
        # Wait for cooldown to expire
        time.sleep(1.1)
        
        # Should be able to process again
        assert handler._should_process(test_path) is True


class TestEndToEndScenarios:
    """End-to-end integration tests simulating real usage scenarios."""
    
    def test_bulk_photo_processing(self, tmp_path):
        """Test processing a directory with many photos like a camera import."""
        photo_dir = tmp_path / "camera_import"
        photo_dir.mkdir()
        
        factory = TestImageFactory()
        
        # Simulate importing photos from a camera with various sizes
        photo_files = []
        for i in range(5):
            # Create photos with realistic camera sizes and quality
            photo_path = photo_dir / f"IMG_{i:04d}.jpg"
            info = factory.create_jpeg(
                photo_path, 
                size=(3264, 2448),  # Typical camera resolution
                quality=95  # High quality from camera
            )
            photo_files.append(info)
        
        # Process with typical compression settings
        compressor = Compressor(jpeg_quality=75)  # Good balance of quality/size
        
        total_original = 0
        total_compressed = 0
        
        for photo_info in photo_files:
            path = photo_info['path']
            original_size = path.stat().st_size
            total_original += original_size
            
            stats = compressor.compress(path)
            assert stats is not None
            assert stats['new'] < stats['orig']  # Should achieve compression
            
            total_compressed += stats['new']
            
            # Verify image quality is maintained
            with Image.open(path) as img:
                assert img.size == photo_info['size']
                assert img.format == 'JPEG'
        
        # Should achieve significant overall compression
        compression_ratio = total_compressed / total_original
        assert compression_ratio < 0.8, f"Insufficient bulk compression: {compression_ratio}"
        
        print(f"Bulk compression: {total_original} -> {total_compressed} "
              f"({compression_ratio:.2%} of original)")
    
    def test_mixed_format_directory(self, tmp_path):
        """Test processing a directory with mixed image formats."""
        mixed_dir = tmp_path / "mixed_formats"
        mixed_dir.mkdir()
        
        factory = TestImageFactory()
        
        # Create various formats as might be found in a typical directory
        files = [
            factory.create_jpeg(mixed_dir / "photo.jpg", size=(1200, 800)),
            factory.create_png(mixed_dir / "screenshot.png", size=(1920, 1080)),
            factory.create_webp(mixed_dir / "optimized.webp", size=(800, 600)),
            factory.create_jpeg(mixed_dir / "thumbnail.jpg", size=(150, 150)),
        ]
        
        # Add a non-image file that should be ignored
        (mixed_dir / "readme.txt").write_text("This is not an image")
        
        # Use watcher to process the directory
        compressed_files = []
        
        class TrackingCompressor:
            def __init__(self):
                self.base_compressor = Compressor(jpeg_quality=70, webp_quality=75)
            
            def compress(self, path: Path):
                result = self.base_compressor.compress(path)
                if result:
                    compressed_files.append(path.name)
                return result
        
        handler = ImageHandler(
            compressor=TrackingCompressor(),
            stable_seconds=0.1,
            new_delay=0,
            cooldown=0,
            compress_timeout=10.0
        )
        handler.workers = 2  # Test with multiple workers
        
        # Process all files
        process_existing(mixed_dir, handler)
        
        # Wait for all processing to complete
        time.sleep(1.0)
        
        # Should have processed only image files
        expected_images = {"photo.jpg", "screenshot.png", "optimized.webp", "thumbnail.jpg"}
        assert set(compressed_files) == expected_images
        
        # Verify all images still exist and are valid
        for file_info in files:
            path = file_info['path']
            assert path.exists()
            with Image.open(path) as img:
                assert img.size == file_info['size']
    
    def test_concurrent_file_creation(self, tmp_path):
        """Test handling concurrent file creation like a download folder."""
        download_dir = tmp_path / "downloads"
        download_dir.mkdir()
        
        processed_files = []
        processing_lock = threading.Lock()
        
        class ConcurrentCompressor:
            def compress(self, path: Path):
                # Simulate some processing time
                time.sleep(0.1)
                with processing_lock:
                    processed_files.append(path.name)
                
                original_size = path.stat().st_size
                return {
                    'orig': original_size,
                    'new': int(original_size * 0.7),
                    'saved': int(original_size * 0.3)
                }
        
        handler = ImageHandler(
            compressor=ConcurrentCompressor(),
            stable_seconds=0.1,
            new_delay=0.1,
            cooldown=0.1,
            compress_timeout=5.0
        )
        handler.workers = 3  # Multiple workers for concurrent processing
        
        # Simulate concurrent file downloads
        def create_download_file(name: str, delay: float):
            time.sleep(delay)
            path = download_dir / name
            TestImageFactory.create_jpeg(path, size=(600, 400))
            return path
        
        # Create files concurrently
        threads = []
        file_names = ["download1.jpg", "download2.jpg", "download3.jpg", "download4.jpg"]
        
        for i, name in enumerate(file_names):
            thread = threading.Thread(
                target=create_download_file, 
                args=(name, i * 0.1)
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all files to be created
        for thread in threads:
            thread.join()
        
        # Process the directory
        process_existing(download_dir, handler)
        
        # Wait for all processing to complete
        time.sleep(2.0)
        
        # All files should have been processed
        assert set(processed_files) == set(file_names)


class TestErrorHandling:
    """Test error handling in integration scenarios."""
    
    def test_corrupted_image_handling(self, tmp_path):
        """Test handling of corrupted image files."""
        test_dir = tmp_path / "corrupted_test"
        test_dir.mkdir()
        
        # Create a corrupted "image" file
        corrupted_path = test_dir / "corrupted.jpg"
        corrupted_path.write_bytes(b"This is not a valid JPEG file")
        
        # Create a valid image for comparison
        valid_path = test_dir / "valid.jpg"
        TestImageFactory.create_jpeg(valid_path, size=(200, 200))
        
        compressor = Compressor(jpeg_quality=70)
        
        # Valid image should compress successfully
        valid_stats = compressor.compress(valid_path)
        assert valid_stats is not None
        
        # Corrupted image should fail gracefully
        corrupted_stats = compressor.compress(corrupted_path)
        assert corrupted_stats is None  # Should return None for failed compression
    
    def test_permission_denied_handling(self, tmp_path):
        """Test handling of permission denied errors."""
        test_dir = tmp_path / "permission_test"
        test_dir.mkdir()
        
        # Create a test image
        image_path = test_dir / "readonly.jpg"
        TestImageFactory.create_jpeg(image_path, size=(200, 200))
        
        # Make the file read-only (simulate permission issue)
        image_path.chmod(0o444)  # Read-only
        
        compressor = Compressor(jpeg_quality=70)
        
        try:
            # This should handle the permission error gracefully
            stats = compressor.compress(image_path)
            # On some systems this might succeed (if we can still write),
            # on others it should fail gracefully
            if stats is None:
                # Failed gracefully as expected
                pass
            else:
                # Succeeded despite read-only (some filesystems allow this)
                assert 'orig' in stats
                assert 'new' in stats
        finally:
            # Restore permissions for cleanup
            try:
                image_path.chmod(0o644)
            except:
                pass


if __name__ == "__main__":
    # Allow running integration tests directly
    pytest.main([__file__, "-v"])
