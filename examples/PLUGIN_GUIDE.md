# imgc Plugin Development Guide

imgc supports a powerful plugin system that allows you to extend its functionality beyond image processing to handle any file type. This guide shows you how to create your own plugins.

## Quick Start

### 1. Plugin Directory
Create your plugins in the default plugin directory next to the imgc executable:
- **Default**: `./plugins/` (relative to imgc executable or main.py)
- **Custom**: Use `--plugin-dirs` to specify additional directories
- **Legacy**: Previous versions used `~/.imgc/plugins/` (still supported with `--plugin-dirs`)

### 2. Basic Plugin Structure
```python
# my_plugin.py
import sys
from pathlib import Path

# Standard imports for imgc plugins
try:
    from imgc.plugin_api import FileProcessor, ProcessorResult
except ImportError:
    # Fallback for standalone testing
    imgc_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(imgc_root))
    from imgc.plugin_api import FileProcessor, ProcessorResult


class MyProcessor(FileProcessor):
    @property
    def name(self):
        return "My Custom Processor"
    
    @property
    def supported_extensions(self):
        return [".txt", ".log"]  # File types you want to handle
    
    def process(self, file_path, context):
        # Your processing logic here
        try:
            # Do something with the file
            result = f"Processed {file_path.name}"
            
            return ProcessorResult(
                success=True,
                message=result,
                stats={"processed": True},
                context={"my_plugin_ran": True}
            )
        except Exception as e:
            return ProcessorResult(
                success=False,
                message=f"Processing failed: {e}"
            )
```

### 3. Install and Test
1. Save your plugin as `./plugins/my_plugin.py` (next to imgc executable)
2. Restart imgc or use `--plugin-dirs ./plugins` if running from different directory
3. Your plugin will automatically process matching files!

**Alternative locations:**
- Use `--plugin-dirs /custom/path` to load from custom directories
- Multiple directories: `--plugin-dirs ./plugins /another/dir`

## Plugin API Reference

### Required Methods

#### `name` (property)
```python
@property
def name(self):
    return "Human-readable plugin name"
```

#### `supported_extensions` (property)
```python
@property
def supported_extensions(self):
    return [".txt", ".md", ".log"]  # List of file extensions
```

#### `process(file_path, context)`
```python
def process(self, file_path, context):
    # file_path: pathlib.Path object
    # context: dict with data from previous processors
    
    return ProcessorResult(
        success=True,           # bool: whether processing succeeded
        message="Done!",        # str: human-readable result message
        stats={"count": 42},    # dict: any statistics or metrics
        context={"done": True}  # dict: data for next processors
    )
```

### Optional Methods

#### `priority` (property)
```python
@property
def priority(self):
    return 100  # Lower numbers run first (default: 100)
```

#### `version` (property)
```python
@property
def version(self):
    return "1.0.0"  # Your plugin version
```

#### `description` (property)
```python
@property
def description(self):
    return "What this plugin does"
```

#### `can_process(file_path)`
```python
def can_process(self, file_path):
    # Custom logic to determine if this plugin should process the file
    # Default implementation checks file extension
    if not super().can_process(file_path):
        return False
    
    # Add your custom checks here
    return file_path.stat().st_size < 1024 * 1024  # Only files < 1MB
```

## Examples

### Text File Analyzer
```python
class TextAnalyzer(FileProcessor):
    @property
    def name(self):
        return "Text Analyzer"
    
    @property
    def supported_extensions(self):
        return [".txt", ".md", ".rst"]
    
    def process(self, file_path, context):
        with open(file_path, 'r') as f:
            content = f.read()
        
        words = len(content.split())
        lines = len(content.split('\n'))
        chars = len(content)
        
        return ProcessorResult(
            success=True,
            message=f"Analyzed: {words} words, {lines} lines",
            stats={"words": words, "lines": lines, "chars": chars}
        )
```

### File Backup Plugin
```python
class BackupProcessor(FileProcessor):
    @property
    def name(self):
        return "File Backup"
    
    @property
    def supported_extensions(self):
        return [".doc", ".pdf", ".xlsx"]  # Important documents
    
    @property
    def priority(self):
        return 10  # Run first (before other processors)
    
    def process(self, file_path, context):
        import shutil
        
        backup_dir = Path.home() / "backups"
        backup_dir.mkdir(exist_ok=True)
        
        backup_path = backup_dir / file_path.name
        shutil.copy2(file_path, backup_path)
        
        return ProcessorResult(
            success=True,
            message=f"Backed up to {backup_path}",
            context={"backed_up": True}
        )
```

### External Tool Integration
```python
class PDFOptimizer(FileProcessor):
    @property
    def name(self):
        return "PDF Optimizer"
    
    @property
    def supported_extensions(self):
        return [".pdf"]
    
    def can_process(self, file_path):
        # Check if required tool is available
        import shutil
        return super().can_process(file_path) and shutil.which('gs')  # Ghostscript
    
    def process(self, file_path, context):
        import subprocess
        
        output_path = file_path.with_suffix('.optimized.pdf')
        
        cmd = [
            'gs',
            '-sDEVICE=pdfwrite',
            '-dCompatibilityLevel=1.4',
            '-dPDFSETTINGS=/screen',
            '-dNOPAUSE', '-dQUIET', '-dBATCH',
            f'-sOutputFile={output_path}',
            str(file_path)
        ]
        
        try:
            subprocess.run(cmd, check=True, timeout=60)
            
            # Replace original if smaller
            original_size = file_path.stat().st_size
            new_size = output_path.stat().st_size
            
            if new_size < original_size:
                output_path.replace(file_path)
                saved = original_size - new_size
                return ProcessorResult(
                    success=True,
                    message=f"PDF optimized: saved {saved} bytes",
                    stats={"original_size": original_size, "new_size": new_size}
                )
            else:
                output_path.unlink()  # Remove if no improvement
                return ProcessorResult(
                    success=True,
                    message="PDF already optimized"
                )
                
        except Exception as e:
            return ProcessorResult(
                success=False,
                message=f"PDF optimization failed: {e}"
            )
```

## Best Practices

### 1. Error Handling
Always wrap your processing logic in try/except blocks:
```python
def process(self, file_path, context):
    try:
        # Your processing code
        return ProcessorResult(success=True, message="Success!")
    except Exception as e:
        return ProcessorResult(success=False, message=f"Error: {e}")
```

### 2. File Validation
Check files before processing:
```python
def can_process(self, file_path):
    if not super().can_process(file_path):
        return False
    
    # Check file size, permissions, etc.
    try:
        size = file_path.stat().st_size
        return 0 < size < 100 * 1024 * 1024  # 0-100MB range
    except:
        return False
```

### 3. Temporary Files
Use temporary files for processing:
```python
def process(self, file_path, context):
    temp_path = file_path.with_suffix('.temp')
    try:
        # Process file_path -> temp_path
        # ... processing logic ...
        
        # Replace original with processed version
        temp_path.replace(file_path)
        
        return ProcessorResult(success=True, message="Processed!")
    finally:
        # Clean up temp file if it still exists
        if temp_path.exists():
            temp_path.unlink()
```

### 4. Resource Limits
Set reasonable timeouts and limits:
```python
def process(self, file_path, context):
    # Check file size
    if file_path.stat().st_size > 50 * 1024 * 1024:  # 50MB limit
        return ProcessorResult(success=False, message="File too large")
    
    # Use timeouts for external commands
    subprocess.run(cmd, timeout=30)  # 30 second timeout
```

### 5. Testing Your Plugin
Add a test section to your plugin:
```python
if __name__ == "__main__":
    # Test your plugin
    processor = MyProcessor()
    print(f"Plugin: {processor.name}")
    print(f"Supports: {processor.supported_extensions}")
    
    # Test with a sample file
    test_file = Path("sample.txt")
    if test_file.exists() and processor.can_process(test_file):
        result = processor.process(test_file, {})
        print(f"Test result: {result.message}")
```

## Plugin Chain Behavior

- Plugins run in **priority order** (lower numbers first)
- Each plugin receives the **context** from previous plugins
- If a plugin fails, the chain continues with other plugins
- Plugin failures are logged but don't stop file processing

## Debugging

### Enable Debug Logging
Set the log level to debug to see plugin loading and execution details:
```bash
imgc --log-level debug --root /path/to/watch
```

### Test Plugin Loading
```python
from imgc.plugin_manager import PluginManager

manager = PluginManager()
manager.discover_plugins()
stats = manager.get_stats()

print("Loaded plugins:", [p['name'] for p in stats['processors']])
print("Failed plugins:", stats['failed'])
```

## Advanced Features

### Multiple Processors Per File
You can define multiple processor classes in one plugin file:
```python
class TextProcessor(FileProcessor):
    # ... implementation ...

class LogProcessor(FileProcessor):
    # ... implementation ...
```

### Configuration
Read configuration from environment variables or files:
```python
import os

class ConfigurableProcessor(FileProcessor):
    def __init__(self):
        self.quality = int(os.getenv('MY_PLUGIN_QUALITY', '80'))
        self.enabled = os.getenv('MY_PLUGIN_ENABLED', 'true').lower() == 'true'
```

### Plugin Arguments
Plugins can declare CLI arguments and environment variables:
```python
from imgc.plugin_api import FileProcessor, ProcessorResult, PluginArgument

class ConfigurableProcessor(FileProcessor):
    def __init__(self):
        # Set default values (will be overridden by configure_from_args)
        self.quality = 80
        self.enabled = True
    
    @property
    def name(self):
        return "My Processor"
    
    @property
    def supported_extensions(self):
        return [".txt"]
    
    def get_plugin_arguments(self):
        """Declare CLI arguments for this plugin."""
        return [
            PluginArgument("quality", int, 80, "Processing quality (1-100)"),
            PluginArgument("enabled", bool, True, "Enable processing")
        ]
    
    def get_plugin_namespace(self):
        """Use custom namespace (default: auto-generated from name)."""
        return "my-proc"  # Creates --my-proc-quality, --my-proc-enabled
    
    def process(self, file_path, context):
        if not self.enabled:
            return ProcessorResult(success=True, message="Disabled")
        
        # Use self.quality in processing logic
        return ProcessorResult(success=True, message=f"Processed with quality {self.quality}")
```

**Usage:**
```bash
# CLI arguments (auto-generated from plugin)
imgc --root /path --my-proc-quality 90 --my-proc-enabled

# Environment variables (auto-generated)
export IMGC_MY_PROC_QUALITY=90
export IMGC_MY_PROC_ENABLED=true
imgc --root /path
```

### Context Passing
Use context to coordinate between plugins:
```python
def process(self, file_path, context):
    # Check what previous plugins did
    if context.get('already_processed'):
        return ProcessorResult(success=True, message="Skipped (already processed)")
    
    # Do processing...
    
    # Mark for next plugins
    return ProcessorResult(
        success=True,
        message="Processed!",
        context={"my_plugin_processed": True}
    )
```

## Need Help?

- Check the example plugins in `examples/plugins/`
- Look at the built-in image processor in `imgc/plugins/builtin/`
- Enable debug logging to see what's happening
- Test your plugins standalone before deploying

Happy plugin development! 🚀
