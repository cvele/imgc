# imgc - Intelligent Image Compression Watcher

[![Build Status](https://github.com/cvele/imgc/actions/workflows/test-build.yml/badge.svg)](https://github.com/cvele/imgc/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

**imgc** is a cross-platform file system watcher that automatically compresses images when they're created or modified. It monitors directories for new image files and applies intelligent compression while preserving quality.

## Features

- 🔍 **Real-time monitoring** - Watches directories for new image files
- 🗜️ **Smart compression** - Optimizes JPEG, PNG, WebP, and AVIF images
- ⚡ **Multi-threaded** - Processes multiple images concurrently
- 🛡️ **Stable file detection** - Waits for file writes to complete before processing
- 🔄 **Cross-platform** - Works on Windows, macOS, and Linux
- ⏱️ **Configurable timeouts** - Prevents hanging on problematic files
- 📊 **Detailed logging** - Shows compression statistics and savings
- 🚫 **Cooldown periods** - Prevents repeated processing of the same files

## Quick Start

### Download Binary

Download the latest release for your platform from [Releases](https://github.com/cvele/imgc/releases):

> **Note**: Replace `cvele` with the actual GitHub username/organization

- **Linux**: `imgc-linux-x64` or `imgc-linux-arm64`
- **Windows**: `imgc-windows-x64.exe` or `imgc-windows-arm64.exe`
- **macOS**: `imgc-macos-x64` or `imgc-macos-arm64`

> **Note**: ARM64 binaries are currently x64 binaries with ARM64 naming due to GitHub Actions limitations. They will work on ARM64 systems through emulation.

### Basic Usage

```bash
# Linux/macOS
chmod +x imgc-linux-x64
./imgc-linux-x64 --root /path/to/watch

# Windows
imgc-windows-x64.exe --root C:\path\to\watch
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
# Watch a directory with default settings
imgc --root /home/user/images

# Custom compression quality
imgc --root /home/user/images --jpeg-quality 85 --webp-quality 80

# Multi-threaded processing with custom timeouts
imgc --root /home/user/images --workers 4 --compress-timeout 30

# Quiet mode with file logging
imgc --root /home/user/images --log-level quiet --log-file imgc.log
```

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `--root` | *required* | Directory to watch for images |
| `--jpeg-quality` | 85 | JPEG compression quality (1-100) |
| `--png-min` | 65 | PNG minimum compression level (0-100) |
| `--png-max` | 80 | PNG maximum compression level (0-100) |
| `--webp-quality` | 85 | WebP compression quality (1-100) |
| `--avif-quality` | 65 | AVIF compression quality (1-100) |
| `--workers` | 1 | Number of worker threads for batch processing |
| `--stable-seconds` | 2.0 | Time to wait for file stability |
| `--new-delay` | 0.0 | Delay before processing new files |
| `--compress-timeout` | 30.0 | Per-file compression timeout (seconds) |
| `--log-level` | info | Logging level: debug, info, warning, quiet |

### Environment Variables

All options can be set via environment variables with the `IMGC_` prefix:

```bash
export IMGC_ROOT="/home/user/images"
export IMGC_JPEG_QUALITY=90
export IMGC_WORKERS=4
imgc  # Uses environment variables
```

## Supported Formats

- **JPEG** (.jpg, .jpeg) - Quality-based compression
- **PNG** (.png) - Lossless optimization with configurable compression levels
- **WebP** (.webp) - Modern format with excellent compression
- **AVIF** (.avif) - Next-generation format with superior compression

## Development

### Requirements

- Python 3.8+
- See `requirements.txt` for dependencies

### Development Setup

```bash
# Clone and setup
git clone https://github.com/cvele/imgc.git
cd imgc
make install    # Creates venv and installs all dependencies

# Run tests
make test       # Runs pytest in the venv

# Build binary
make build      # Creates standalone executable

# Format code
make format     # Formats code with black
```

### Available Make Targets

```bash
make help                              # Show all targets
make run ARGS="--root /path"           # Run with arguments
make test                              # Run test suite
make build                             # Build standalone binary
make release VERSION=v1.0.0           # Create release
make clean                             # Clean build artifacts
```

## How It Works

1. **Monitoring**: Uses the `watchdog` library to monitor file system events
2. **Detection**: Identifies image files by extension and waits for stability
3. **Processing**: Applies format-specific compression using Pillow
4. **Optimization**: Reduces file size while maintaining visual quality
5. **Reporting**: Logs compression statistics and space savings

## Performance

- **Lightweight**: Minimal resource usage when idle
- **Efficient**: Only processes new or modified files
- **Scalable**: Configurable worker threads for batch processing
- **Robust**: Timeout handling prevents hanging on problematic files

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
