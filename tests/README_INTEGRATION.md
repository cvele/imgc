# Integration Tests for imgc

This document describes the integration test suite for imgc, which tests the complete image compression workflow with real image files.

## Overview

The integration tests (`test_integration.py`) complement the unit tests by testing:

- Real image compression with actual image files
- File watcher integration with real images
- End-to-end scenarios simulating real-world usage
- Error handling with corrupted/problematic files

## Test Structure

### TestImageFactory
A factory class for creating test images in various formats:

- **JPEG**: Creates realistic photos with grid patterns and text
- **PNG**: Creates images with transparency effects
- **WebP**: Creates images with gradient effects

All created images have realistic content to ensure meaningful compression tests.

### Test Categories

#### 1. TestImageCompression
Tests core compression functionality:

- `test_compress_various_formats`: Tests compression of JPEG, PNG, and WebP files
- `test_compression_preserves_metadata`: Ensures image properties are maintained
- `test_compression_with_different_qualities`: Tests quality setting effects

#### 2. TestWatcherIntegration
Tests file watcher with real images:

- `test_watcher_processes_new_images`: Verifies watcher processes new image files
- `test_watcher_respects_cooldown`: Tests cooldown period functionality

#### 3. TestEndToEndScenarios
Real-world usage scenarios:

- `test_bulk_photo_processing`: Simulates camera import with high-resolution photos
- `test_mixed_format_directory`: Tests directory with mixed image formats
- `test_concurrent_file_creation`: Tests concurrent file processing (download folder scenario)

#### 4. TestErrorHandling
Error scenarios:

- `test_corrupted_image_handling`: Tests graceful handling of corrupted image files
- `test_permission_denied_handling`: Tests read-only file scenarios

## Running Integration Tests

### Make Targets

```bash
# Run only integration tests
make test-integration

# Run only unit tests (excludes integration)
make test-unit

# All tests
make test
```

### Direct pytest Commands

```bash
# Run integration tests with verbose output
pytest tests/test_integration.py -v

# Run specific test class
pytest tests/test_integration.py::TestImageCompression -v

# Run specific test method
pytest tests/test_integration.py::TestImageCompression::test_compress_various_formats -v
```

## Test Data

Integration tests create temporary image files during execution:

- **Formats**: JPEG, PNG, WebP
- **Sizes**: From 150x150 thumbnails to 3264x2448 camera photos
- **Content**: Realistic patterns, gradients, transparency effects
- **Quality**: Various quality settings to test compression behavior

All test images are created in temporary directories and cleaned up automatically.

## Performance Considerations

Integration tests are slower than unit tests because they:

- Create real image files with PIL
- Perform actual compression operations
- Test file I/O and threading
- Include deliberate delays for cooldown testing

Typical execution time: 5-8 seconds for all integration tests.

## Maintenance Notes

### Adding New Tests

1. Use `TestImageFactory` for creating test images
2. Follow existing patterns for temporary directories (`tmp_path` fixture)
3. Test both success and failure scenarios
4. Include realistic image sizes and content
5. Clean up any created files (handled automatically by pytest)

### Test Isolation

Each test method runs in isolation with:

- Fresh temporary directories
- Independent image files
- Separate compressor instances
- No shared state between tests

### Debugging Integration Tests

For debugging failed integration tests:

1. Run with verbose output: `pytest tests/test_integration.py -v -s`
2. Check temporary directory contents (printed in verbose mode)
3. Verify image file creation and compression results
4. Use logging output to trace execution flow

## Integration with CI/CD

The integration tests are designed to run in CI environments:

- No external dependencies beyond PIL and pytest
- Self-contained image generation
- Deterministic behavior (no random elements)
- Reasonable execution time
- Cross-platform compatibility

## Coverage

Integration tests provide coverage for:

- Real image compression workflows
- File watcher event handling
- Multi-threading scenarios
- Error handling with real files
- Performance characteristics
- Cross-format compatibility

These tests complement the unit tests to ensure imgc works correctly in real-world scenarios.
