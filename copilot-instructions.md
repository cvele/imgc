# GitHub Copilot Instructions for imgc

This file provides context and guidelines for GitHub Copilot to assist with code reviews, suggestions, and development of the imgc (Intelligent Image Compression Watcher) project.

## Project Overview

**imgc** is a cross-platform file system watcher that automatically compresses images when they're created or modified. It's designed for efficiency, reliability, and ease of use.

### Core Technologies
- **Python 3.8+** - Main language
- **Pillow (PIL)** - Image processing and compression
- **watchdog** - File system monitoring
- **PyInstaller** - Standalone binary creation
- **pytest** - Testing framework

### Architecture
- **main.py** - CLI entry point with argument parsing and path validation
- **imgc/watcher.py** - Core file watching and event handling logic
- **imgc/compressor.py** - Image compression algorithms and optimization
- **imgc/config.py** - Centralized configuration defaults
- **imgc/cli.py** - Alternative CLI interface
- **imgc/logging_config.py** - Logging setup and configuration

## Code Review Guidelines

### Code Quality Standards

1. **Type Hints**: All functions should have proper type hints
   ```python
   # Good
   def compress_image(path: Path, quality: int = 85) -> Optional[Dict[str, int]]:
   
   # Avoid
   def compress_image(path, quality=85):
   ```

2. **Error Handling**: Always handle exceptions gracefully
   ```python
   # Good
   try:
       result = compressor.compress(path)
   except Exception as e:
       logger.warning('Compression failed for %s: %s', path, e)
       return None
   
   # Avoid silent failures
   result = compressor.compress(path)  # Could raise unhandled exception
   ```

3. **Logging**: Use appropriate log levels and structured messages
   ```python
   # Good
   logger.info('Compressed %s: %s -> %s (%.1f%% saved)', 
              path.name, orig_size, new_size, percent_saved)
   
   # Avoid
   print(f"Done: {path}")
   ```

4. **Path Handling**: Always use `pathlib.Path` for cross-platform compatibility
   ```python
   # Good
   path = Path(user_input).resolve()
   
   # Avoid
   path = os.path.join(root, filename)
   ```

### Project-Specific Patterns

1. **Configuration**: Use centralized config with environment variable support
   ```python
   # Follow this pattern from config.py
   DEFAULT_JPEG_QUALITY = 70
   
   # In main.py
   env_jpeg = _env_int('IMGC_JPEG_QUALITY', config.DEFAULT_JPEG_QUALITY)
   ```

2. **Threading**: Use daemon threads for background processing
   ```python
   # Good
   bg = threading.Thread(target=process_existing, args=(root, handler), daemon=True)
   bg.start()
   ```

3. **Signal Handling**: Always support graceful shutdown
   ```python
   # Follow the pattern in watcher.py
   def _on_signal(signum, frame):
       logger.info('Signal %s received, shutting down...', signum)
       stop_event.set()
   ```

4. **Cross-Platform Compatibility**: Consider Windows, macOS, and Linux
   ```python
   # Good - handles platform differences
   if sys.platform.startswith('win'):
       # Windows-specific code
   else:
       # POSIX systems
   ```

### Testing Guidelines

1. **Test Coverage**: All new features must have comprehensive tests
   - Unit tests for individual functions
   - Integration tests for workflows
   - Edge case testing (empty directories, invalid paths, etc.)

2. **Test Structure**: Follow existing patterns
   ```python
   def test_feature_name(monkeypatch, tmp_path, caplog):
       """Test description explaining what is being tested."""
       # Setup
       # Action
       # Assertion
   ```

3. **Test the Actual Implementation**: Avoid reimplementing logic in tests
   ```python
   # Good - Test the actual function
   from main import _env_bool
   result = _env_bool('TEST_VAR', False)
   assert result == expected
   
   # Avoid - Reimplementing the logic
   def _env_str(name, default=None):  # Duplicates main.py logic
       return env.get(name, default)
   result = _env_str('TEST_VAR', 'false').lower() in ('true', '1', 'yes', 'on')
   ```

4. **Mocking**: Use pytest's monkeypatch for clean mocking
   ```python
   # Good
   monkeypatch.setattr(module, 'function', mock_function)
   
   # Avoid complex manual mocking
   ```

5. **Temporary Files**: Always use pytest's tmp_path fixture
   ```python
   def test_file_processing(tmp_path):
       test_file = tmp_path / 'test.jpg'
       test_file.write_bytes(b'fake_image_data')
   ```

6. **Extract Testable Functions**: Make code more testable by extracting pure functions
   ```python
   # Good - Extracted, testable function
   def _env_bool(name, default=False):
       return _env_str(name, 'false' if not default else 'true').lower() in ('true', '1', 'yes', 'on')
   
   # Then test it directly
   def test_env_bool_parsing():
       assert _env_bool('TEST', False) == expected
   ```

### Performance Considerations

1. **File I/O**: Minimize file system operations
2. **Threading**: Use appropriate worker counts for CPU-bound tasks
3. **Memory**: Process images one at a time to avoid memory spikes
4. **Timeouts**: Always implement timeouts for potentially long operations

### Security Considerations

1. **Path Traversal**: Validate and normalize all user-provided paths
2. **File Permissions**: Check file accessibility before processing
3. **Resource Limits**: Implement timeouts and size limits
4. **Input Validation**: Sanitize all user inputs

## Common Patterns to Suggest

### 1. Image Processing
```python
def process_image(path: Path, compressor: Compressor) -> Optional[Dict[str, int]]:
    """Process a single image file with proper error handling."""
    try:
        if not path.exists() or not path.is_file():
            return None
        
        stats = compressor.compress(path)
        if stats:
            logger.info('Processed %s: saved %s bytes', path.name, stats.get('saved', 0))
        return stats
    except Exception as e:
        logger.warning('Failed to process %s: %s', path, e)
        return None
```

### 2. Configuration Loading
```python
def load_config_value(env_name: str, default_value, value_type=str):
    """Load configuration from environment with type conversion."""
    env_value = os.environ.get(env_name)
    if env_value is None:
        return default_value
    
    try:
        if value_type == bool:
            return env_value.lower() in ('true', '1', 'yes', 'on')
        return value_type(env_value)
    except (ValueError, TypeError):
        logger.warning('Invalid %s value: %s, using default: %s', 
                      env_name, env_value, default_value)
        return default_value
```

### 3. File System Watching
```python
def create_handler(compressor: Compressor, **kwargs) -> ImageHandler:
    """Create a properly configured image handler."""
    handler = ImageHandler(compressor, **kwargs)
    handler.stop_event = threading.Event()
    return handler
```

## Code Review Checklist

When reviewing code, check for:

### Functionality
- [ ] Does the code handle the happy path correctly?
- [ ] Are edge cases handled (empty files, missing directories, permissions)?
- [ ] Is error handling comprehensive and user-friendly?

### Performance
- [ ] Are file operations minimized?
- [ ] Is threading used appropriately?
- [ ] Are there any memory leaks or resource leaks?

### Reliability
- [ ] Is the code robust against malformed inputs?
- [ ] Are timeouts implemented for long operations?
- [ ] Is graceful shutdown supported?

### Maintainability
- [ ] Is the code self-documenting with clear variable names?
- [ ] Are functions single-purpose and reasonably sized?
- [ ] Is there appropriate logging for debugging?

### Testing
- [ ] Are there tests covering the new functionality?
- [ ] Do tests cover both success and failure cases?
- [ ] Are tests isolated and repeatable?

### Cross-Platform
- [ ] Does the code work on Windows, macOS, and Linux?
- [ ] Are path operations using `pathlib.Path`?
- [ ] Are platform-specific features properly conditionally handled?

## Anti-Patterns to Avoid

1. **Global State**: Avoid global variables; use dependency injection
2. **Hardcoded Paths**: Always use configurable paths
3. **Silent Failures**: Always log errors and provide feedback
4. **Blocking Operations**: Use timeouts for file I/O and network operations
5. **Platform Assumptions**: Don't assume Unix-only or Windows-only environments
6. **Magic Numbers**: Use named constants from config.py
7. **Complex Inheritance**: Prefer composition over inheritance
8. **Tight Coupling**: Keep modules loosely coupled and testable

## Preferred Libraries and Patterns

### File Operations
- **Use**: `pathlib.Path` for all path operations
- **Use**: `shutil` for file operations
- **Avoid**: `os.path` (legacy, not cross-platform)

### Concurrency
- **Use**: `threading.Thread` with daemon=True for background tasks
- **Use**: `concurrent.futures.ThreadPoolExecutor` for parallel processing
- **Use**: `threading.Event` for signaling
- **Avoid**: `multiprocessing` (overkill for I/O bound tasks)

### Configuration
- **Use**: Environment variables with `IMGC_` prefix
- **Use**: Centralized defaults in `config.py`
- **Use**: Type conversion with error handling

### Testing
- **Use**: `pytest` fixtures (`tmp_path`, `monkeypatch`, `caplog`)
- **Use**: Descriptive test names that explain the scenario
- **Use**: Arrange-Act-Assert pattern

## Build and Release Considerations

1. **PyInstaller**: When adding new dependencies, update hidden imports in Makefile
2. **Cross-Platform**: Test builds on Windows, macOS, and Linux
3. **Dependencies**: Keep requirements.txt minimal and well-documented
4. **Versioning**: Follow semantic versioning for releases
5. **Documentation**: Update README.md and CHANGELOG.md for all user-facing changes

## Common Issues to Watch For

1. **PIL Import Errors**: Ensure PyInstaller includes all PIL submodules
2. **Path Separators**: Use `pathlib.Path` to handle Windows vs POSIX differences
3. **Signal Handling**: Windows doesn't support SIGTERM, handle gracefully
4. **File Locking**: Wait for file stability before processing
5. **Resource Cleanup**: Always clean up threads, file handles, and observers

## Performance Optimization Opportunities

1. **Batch Processing**: Group file operations when possible
2. **Lazy Loading**: Only load heavy dependencies when needed
3. **Caching**: Cache file modification times to avoid repeated processing
4. **Streaming**: Process large files in chunks if needed
5. **Debouncing**: Use cooldown periods to avoid excessive processing

This document should help GitHub Copilot provide more contextually appropriate suggestions and catch potential issues during code reviews.
