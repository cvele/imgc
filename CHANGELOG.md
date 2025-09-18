# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v0.1.0]

### Added
- **Plugin System**: Complete rewrite with extensible plugin architecture
  - Plugin API with `FileProcessor` base class for custom file processors
  - Plugin Manager with automatic plugin discovery and loading
  - Built-in plugin system with modular image processing
  - Plugin argument system with CLI integration and environment variable support
  - Plugin namespacing to prevent argument conflicts between plugins
  - Plugin validation and error handling with detailed logging
- **Plugin Arguments**: Plugins can declare their own CLI arguments and environment variables
  - Automatic argument parsing and configuration
  - Type-safe argument definitions (int, float, bool, string)
  - Environment variable support with `IMGC_<PLUGIN>_<ARGUMENT>` naming convention
  - Argument help text integration with main CLI help system
- **Enhanced Image Processing**: ImageProcessor now configurable via plugin arguments
  - `--image-jpeg-quality` (default: 85) - JPEG compression quality (1-100)
  - `--image-png-min` (default: 65) - PNG minimum compression level (0-100) 
  - `--image-png-max` (default: 80) - PNG maximum compression level (0-100)
  - `--image-webp-quality` (default: 85) - WebP compression quality (1-100)
  - `--image-avif-quality` (default: 65) - AVIF compression quality (1-100)
- **Plugin Directory Management**: Improved plugin discovery and loading
  - Default plugin directory next to executable (`./plugins`) instead of home directory
  - Built-in plugins always included regardless of custom directories
  - `--plugin-dirs` argument for specifying custom plugin locations
- **Examples and Documentation**: Comprehensive plugin development resources
  - Example plugins: document processor, video processor
  - Detailed Plugin Guide with step-by-step instructions
  - Plugin API documentation with examples and best practices
- **Testing Infrastructure**: Complete test suite for plugin system
  - Unit tests for plugin API, manager, and argument system
  - Integration tests for end-to-end plugin functionality
  - CLI integration tests for argument parsing and help output
  - Plugin validation and error handling tests

### Changed  
- **BREAKING**: Complete architecture rewrite from hardcoded image processing to plugin system
- **BREAKING**: Removed hardcoded compression quality arguments (now plugin-based)
- **BREAKING**: Plugin directories now default to `./plugins`
- **BREAKING**: Removed old CLI module (`imgc/cli.py`) and compressor module (`imgc/compressor.py`)
- Main entry point (`main.py`) completely rewritten for plugin system integration
- Two-phase argument parsing: discover plugins first, then add their arguments to parser
- Plugin arguments automatically grouped in CLI help for better organization
- Environment variables now support plugin-specific prefixes for better organization

### Removed
- **BREAKING**: Removed hardcoded image compression logic (`imgc/compressor.py`)
- **BREAKING**: Removed old file watcher implementation (`imgc/watcher.py`) 
- **BREAKING**: Removed old CLI interface (`imgc/cli.py`)
- **BREAKING**: Removed old test files for removed modules
- Removed home directory plugin discovery (`~/.imgc/plugins`)
- Removed system-wide plugin directories (`/opt/imgc/plugins`)

### Fixed
- Plugin argument environment variable parsing with proper type conversion
- Plugin directory creation with proper error handling
- Plugin validation with comprehensive error messages
- Test compatibility with new plugin architecture
- Cross-platform plugin directory detection (development vs executable)

### Technical Details
- Plugin API uses abstract base classes for type safety and validation
- Plugin Manager implements safe plugin loading with syntax validation
- Processor Chain provides timeout handling and error recovery for plugin execution
- Plugin arguments use NamedTuple for structured definition and validation
- Built-in ImageProcessor migrated to plugin system while maintaining full functionality
- Test suite expanded from 99 to 112 tests with comprehensive plugin coverage

## [v0.0.3]

### Added
- Full AVIF format support with imageio integration
- Code coverage reporting with Codecov integration
- Coverage badge in README.md
- Comprehensive integration test suite with real image processing scenarios
- Dependabot configuration for automated dependency updates
- Security-focused Dependabot workflows for vulnerability management
- Coverage configuration file (.coveragerc) for optimized reporting
- Enhanced error handling for AVIF processing with specific ImportError handling

### Changed
- **BREAKING**: imageio is now a required dependency (was optional/commented)
- Upgraded AVIF processing to use imageio v3 API for better reliability
- Enhanced CI workflow to run coverage tests and upload results to Codecov
- Improved README documentation with coverage information and AVIF requirements
- Updated Makefile with coverage target and help text
- Better error messages for AVIF compression failures
- Test suite now expects AVIF compression to succeed (was expecting failure)

### Fixed
- AVIF compression now works reliably with proper imageio v3 API usage
- AVIF quality parameter handling (uses default settings due to imageio limitations)
- Enhanced test coverage across all image processing scenarios

### Technical Details
- imageio v3 API provides cleaner interface: `iio.imwrite(file, data, extension='.avif')`
- Coverage integration generates XML reports for CI and HTML reports for local development
- Dependabot monitors both GitHub Actions and Python dependencies
- Integration tests cover real-world scenarios: bulk processing, concurrent operations, error handling

## [v0.0.2]

### Added
- `--process-existing` flag to enable processing of existing images on startup
- `IMGC_PROCESS_EXISTING` environment variable support
- Watch-only mode as the new default behavior (existing images are skipped)
- Better path validation with helpful error messages

### Changed
- **BREAKING**: Default behavior changed from processing existing images to watch-only mode
- Improved code quality by removing unnecessary `globals()` usage
- Extracted environment variable parsing logic into testable functions
- Made boolean parsing more maintainable with explicit constants

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
