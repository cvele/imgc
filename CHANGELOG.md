# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v0.0.2]

### Added
- `--process-existing` flag to enable processing of existing images on startup
- `IMGC_PROCESS_EXISTING` environment variable support
- Watch-only mode as the new default behavior (existing images are skipped)
- Better path validation with helpful error messages

### Changed
- **BREAKING**: Default behavior changed from processing existing images to watch-only mode
- Improved code quality by removing unnecessary `globals()` usage

### Fixed
- Windows path handling for paths ending with backslashes
- PyInstaller PIL/Pillow dependency inclusion for binary builds

## [v0.0.1]

### Added
- Cross-platform GitHub Actions release workflow
- Support for Windows, Linux, and macOS builds (x64 and ARM64)
- Automatic changelog generation in releases
- Binary checksums in releases

### Changed
- Improved Makefile for cross-platform PyInstaller builds
- Fixed Windows-specific watchdog observer imports

### Fixed
- Test compatibility issues with threading and event handling
- Cross-platform build compatibility
- PyInstaller PIL/Pillow dependency inclusion for binary builds

## [Initial] - Development Version

### Added
- Image compression watcher with support for JPEG, PNG, WebP, and AVIF
- File system monitoring using watchdog
- Configurable compression settings
- Multi-threaded processing
- Signal handling for graceful shutdown
- Comprehensive test suite
- Cross-platform compatibility (Windows, macOS, Linux)

### Features
- Automatic image compression on file creation
- Configurable quality settings for different formats
- Stable file detection (waits for file writes to complete)
- Cooldown periods to prevent repeated processing
- Timeout handling for compression operations
- Detailed logging and progress reporting
