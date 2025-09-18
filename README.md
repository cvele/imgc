# imgc - Universal File Processor with Plugin System

[![Build Status](https://github.com/cvele/imgc/actions/workflows/test-build.yml/badge.svg)](https://github.com/cvele/imgc/actions)
[![Coverage](https://codecov.io/gh/cvele/imgc/branch/main/graph/badge.svg)](https://codecov.io/gh/cvele/imgc)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

**imgc** is a cross-platform file system watcher with an extensible plugin system. While it excels at automatic image compression, its plugin architecture allows you to process any file type with custom logic. Monitor directories for file changes and apply intelligent processing while preserving quality.

## Features

- 🔌 **Plugin System** - Extensible architecture for processing any file type
- 🔍 **Real-time monitoring** - Watches directories for new files
- 🗜️ **Smart image compression** - Built-in support for JPEG, PNG, WebP, and AVIF
- ⚙️ **Configurable processing** - Plugin arguments with CLI and environment variable support
- ⚡ **Multi-threaded** - Processes multiple files concurrently
- 🛡️ **Stable file detection** - Waits for file writes to complete before processing
- 🔄 **Cross-platform** - Works on Windows, macOS, and Linux
- ⏱️ **Configurable timeouts** - Prevents hanging on problematic files
- 📊 **Detailed logging** - Shows processing statistics and results
- 🚫 **Cooldown periods** - Prevents repeated processing of the same files
- 🎯 **Flexible modes** - Watch-only or scan existing files on startup

## Quick Start

### Download Binary

Download the latest release for your platform from [Releases](https://github.com/cvele/imgc/releases):

- **Linux**: `imgc-linux-x64` or `imgc-linux-arm64`
- **Windows**: `imgc-windows-x64.exe` or `imgc-windows-arm64.exe`
- **macOS**: `imgc-macos-x64` or `imgc-macos-arm64`

> **Note**: ARM64 binaries are currently x64 binaries with ARM64 naming due to GitHub Actions limitations. They will work on ARM64 systems through emulation.

### Basic Usage

```bash
# Linux/macOS
chmod +x imgc-linux-x64
./imgc-linux-x64 --root /path/to/watch

# Windows (both formats work)
imgc-windows-x64.exe --root "C:\path\to\watch"
imgc-windows-x64.exe --root C:/path/to/watch
```

### Installation from Source

```bash
git clone https://github.com/cvele/imgc.git
cd imgc
make install                           # Sets up venv and installs dependencies
make run ARGS="--root /path/to/watch"  # Run with arguments
```

## Usage Examples

```bash
# Watch a directory with default settings (watch-only mode)
imgc --root /home/user/images

# Process existing images on startup, then watch for new ones
imgc --root /home/user/images --process-existing

# Custom image compression quality with existing image processing
imgc --root /home/user/images --process-existing --image-jpeg-quality 85 --image-webp-quality 80

# Multi-threaded processing with custom timeouts
imgc --root /home/user/images --process-existing --workers 4 --compress-timeout 30

# Quiet mode with file logging
imgc --root /home/user/images --log-level quiet --log-file imgc.log
```

## Configuration Options

### Core Options

| Option | Default | Description |
|--------|---------|-------------|
| `--root` | *required* | Directory to watch for files |
| `--workers` | 2 | Number of worker threads for batch processing |
| `--stable-seconds` | 2.0 | Time to wait for file stability |
| `--new-delay` | 0.0 | Delay before processing new files |
| `--compress-timeout` | 30.0 | Per-processor timeout (seconds) |
| `--process-existing` | false | Process existing files on startup |
| `--log-level` | info | Logging level: debug, info, warning, quiet |
| `--plugin-dirs` | `./plugins` | Directories to scan for plugins |

### Image Processing Options (Built-in Plugin)

| Option | Default | Description |
|--------|---------|-------------|
| `--image-jpeg-quality` | 85 | JPEG compression quality (1-100) |
| `--image-png-min` | 65 | PNG minimum compression level (0-100) |
| `--image-png-max` | 80 | PNG maximum compression level (0-100) |
| `--image-webp-quality` | 85 | WebP compression quality (1-100) |
| `--image-avif-quality` | 65 | AVIF compression quality (1-100) |

### Environment Variables

All options can be set via environment variables with the `IMGC_` prefix:

```bash
# Core options
export IMGC_ROOT="/home/user/images"
export IMGC_WORKERS=4
export IMGC_PROCESS_EXISTING=true

# Image processing options (plugin arguments use plugin prefix)
export IMGC_IMAGE_JPEG_QUALITY=90
export IMGC_IMAGE_WEBP_QUALITY=80

imgc  # Uses environment variables
```

## Plugin System

imgc uses an extensible plugin architecture that allows you to process any file type:

### Built-in Plugins

- **Image Processor** - Compresses JPEG, PNG, WebP, and AVIF images with configurable quality settings

### Creating Custom Plugins

Create plugins in the `./plugins` directory (or specify custom directories with `--plugin-dirs`):

```python
# ./plugins/my_processor.py
from imgc.plugin_api import FileProcessor, ProcessorResult

class MyProcessor(FileProcessor):
    @property
    def name(self):
        return "My Custom Processor"
    
    @property
    def supported_extensions(self):
        return [".txt", ".log"]
    
    def process(self, file_path, context):
        # Your processing logic here
        return ProcessorResult(success=True, message="Processed!")
```

See the [Plugin Development Guide](examples/PLUGIN_GUIDE.md) for detailed instructions and examples.

## Supported Formats (Built-in Image Plugin)

- **JPEG** (.jpg, .jpeg) - Quality-based compression
- **PNG** (.png) - Lossless optimization with configurable compression levels
- **WebP** (.webp) - Modern format with excellent compression
- **AVIF** (.avif) - Next-generation format with superior compression (requires imageio)

## Development

### Requirements

- Python 3.8+
- **Runtime**: See `requirements.txt` for production dependencies
- **Development**: See `requirements-test.txt` for testing and development tools
- Optional: `pngquant` binary for enhanced PNG compression

### Development Setup

```bash
# Clone and setup
git clone https://github.com/cvele/imgc.git
cd imgc
make install-dev    # Creates venv and installs all dependencies (runtime + test/dev)

# Code quality
make lint           # Check code formatting and syntax
make format         # Format code with black

# Run tests
make test           # Run all tests (unit + integration)
make test-unit      # Run unit tests only (fast)
make coverage       # Run tests with coverage report

# Build binary
make build          # Creates standalone executable (uses runtime deps only)
```

### Available Make Targets

```bash
make help                              # Show all targets
make install                           # Install runtime dependencies only
make install-dev                       # Install runtime + test/dev dependencies
make run ARGS="--root /path"           # Run with arguments
make lint                              # Run code quality checks (formatting, syntax)
make format                            # Format code with black
make test                              # Run all tests (unit + integration)
make test-unit                         # Run unit tests only (fast)
make test-integration                  # Run integration tests only (slower)
make coverage                          # Run tests with coverage report
make build                             # Build standalone binary
make release VERSION=v1.0.0           # Create release
make clean                             # Clean build artifacts
```

## How It Works

1. **Plugin Discovery**: Automatically discovers and loads plugins from configured directories
2. **Monitoring**: Uses the `watchdog` library to monitor file system events
3. **Initial Scan** (optional): Process existing files when `--process-existing` is used
4. **Detection**: Identifies supported files by extension based on loaded plugins
5. **Processing**: Runs applicable plugins in priority order with timeout handling
6. **Chain Execution**: Each plugin receives context from previous plugins
7. **Reporting**: Logs processing statistics and results from all plugins

### Operating Modes

- **Watch-only mode** (default): Only processes new files created after startup
- **Scan + watch mode** (`--process-existing`): Processes existing files first, then watches for new ones

> **⚠️ Breaking Changes**: 
> - **v0.0.2**: Default behavior changed from processing existing files to watch-only mode
> - **Plugin System**: Image quality arguments now use `--image-*` prefix (e.g., `--image-jpeg-quality` instead of `--jpeg-quality`)
> - **Plugin Directories**: Default plugin location changed to `./plugins` 
> 
> **Migration**: 
> - Add `--process-existing` or set `IMGC_PROCESS_EXISTING=true` to restore previous behavior
> - Update quality arguments: `--jpeg-quality` → `--image-jpeg-quality`, etc.
> - Move custom plugins from `~/.imgc/plugins` to `./plugins` or use `--plugin-dirs`

## Real-World Use Case: Plex Media Server Optimization

**Problem**: Large Plex libraries generate massive cache directories filled with uncompressed images (movie posters, thumbnails, artwork). A typical large library can accumulate 300GB+ of cache data, consuming valuable storage space.

**Solution**: Use imgc to automatically compress Plex cache images while maintaining visual quality:

```bash
# Monitor Plex cache directory and compress existing images
imgc --root "/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/Cache" \
     --process-existing \
     --workers 4 \
     --image-jpeg-quality 85 \
     --image-png-min 70 \
     --image-png-max 85

# Or use environment variables for persistent configuration
# Note: Always quote paths containing spaces when setting environment variables
export IMGC_ROOT="/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/Cache"
export IMGC_PROCESS_EXISTING=true
export IMGC_WORKERS=4
export IMGC_IMAGE_JPEG_QUALITY=85
imgc
```

**Results**: 
- **Storage reduction**: 300GB → ~120GB (60% reduction)
- **Quality preserved**: Visually identical images at optimized compression
- **Ongoing optimization**: New cache images automatically compressed
- **Combined with BIF interval reduction**: Further storage savings

> **💡 Pro Tip**: Combine with Plex's BIF (thumbnail) interval settings for maximum storage efficiency while maintaining smooth scrubbing experience.

## Performance

- **Lightweight**: Minimal resource usage when idle (especially in watch-only mode)
- **Efficient**: Only processes new or modified files (with optional existing file processing)
- **Scalable**: Configurable worker threads for batch processing existing files
- **Robust**: Timeout handling prevents hanging on problematic files
- **Fast startup**: Watch-only mode starts monitoring immediately without scanning

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Support

- 🐛 [Issue Tracker](https://github.com/cvele/imgc/issues)

---

**Made with ❤️ for dealing with huge Plex Libraries**
