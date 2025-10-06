"""
Example Document Processor Plugin for imgc.

This is an example of how users can create their own plugins to extend imgc
beyond image processing. This plugin handles text and markdown files.

To use this plugin:
1. Copy this file to ~/.imgc/plugins/
2. Restart imgc
3. The plugin will automatically process .txt and .md files

Author: Example User
Version: 1.0.0
"""

import sys
from pathlib import Path

# This is the standard way to import imgc modules in user plugins
# The plugin manager handles the path setup, but we need this for standalone testing
try:
    from imgc.plugin_api import FileProcessor, ProcessorResult
except ImportError:
    # If running standalone, add the imgc path
    imgc_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(imgc_root))
    from imgc.plugin_api import FileProcessor, ProcessorResult


class DocumentProcessor(FileProcessor):
    """
    A simple document processor that counts words and lines.

    This example shows how to create a basic file processor that:
    - Handles multiple file types
    - Reads file content
    - Performs analysis
    - Returns structured results
    """

    @property
    def name(self):
        return "Document Analyzer"

    @property
    def supported_extensions(self):
        return [".txt", ".md", ".rst", ".log"]

    @property
    def priority(self):
        return 200  # Run after image processors

    @property
    def version(self):
        return "1.0.0"

    @property
    def description(self):
        return "Analyzes text documents and provides word/line counts"

    def process(self, file_path, context):
        """
        Analyze a text document.

        Args:
            file_path: Path to the document file
            context: Context from previous processors

        Returns:
            ProcessorResult with document statistics
        """
        try:
            # Read the file content
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # Analyze the content
            lines = content.split("\n")
            words = content.split()
            characters = len(content)

            # Count non-empty lines
            non_empty_lines = sum(1 for line in lines if line.strip())

            # Calculate averages
            avg_words_per_line = (
                len(words) / non_empty_lines if non_empty_lines > 0 else 0
            )
            avg_chars_per_word = characters / len(words) if words else 0

            # Create statistics
            stats = {
                "total_lines": len(lines),
                "non_empty_lines": non_empty_lines,
                "total_words": len(words),
                "total_characters": characters,
                "avg_words_per_line": round(avg_words_per_line, 1),
                "avg_chars_per_word": round(avg_chars_per_word, 1),
                "file_size": file_path.stat().st_size,
            }

            # Create a summary message
            message = (
                f"Analyzed document: {len(words)} words, {len(lines)} lines, "
                f"{characters} characters"
            )

            return ProcessorResult(
                success=True,
                message=message,
                stats=stats,
                context={"document_analyzed": True, "word_count": len(words)},
            )

        except UnicodeDecodeError:
            return ProcessorResult(
                success=False, message="Could not decode file as text"
            )
        except Exception as e:
            return ProcessorResult(
                success=False, message=f"Document analysis failed: {e}"
            )

    def can_process(self, file_path):
        """
        Enhanced file detection for text documents.

        This example shows how to override can_process for custom logic.
        """
        # First check extension
        if not super().can_process(file_path):
            return False

        # Additional check: ensure file is not too large (> 10MB)
        try:
            file_size = file_path.stat().st_size
            if file_size > 10 * 1024 * 1024:  # 10MB limit
                return False
        except:
            return False

        return True


# You can have multiple processors in one file
class LogProcessor(FileProcessor):
    """
    Example log file processor that extracts error patterns.

    This shows how to create specialized processors for specific use cases.
    """

    @property
    def name(self):
        return "Log Analyzer"

    @property
    def supported_extensions(self):
        return [".log"]

    @property
    def priority(self):
        return 150  # Higher priority than document processor for .log files

    @property
    def description(self):
        return "Analyzes log files for error patterns and statistics"

    def process(self, file_path, context):
        """Analyze log file for error patterns."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            # Count different log levels
            error_count = sum(1 for line in lines if "ERROR" in line.upper())
            warning_count = sum(1 for line in lines if "WARNING" in line.upper())
            info_count = sum(1 for line in lines if "INFO" in line.upper())

            stats = {
                "total_lines": len(lines),
                "error_count": error_count,
                "warning_count": warning_count,
                "info_count": info_count,
                "error_rate": (
                    round((error_count / len(lines)) * 100, 2) if lines else 0
                ),
            }

            message = f"Log analysis: {error_count} errors, {warning_count} warnings in {len(lines)} lines"

            return ProcessorResult(
                success=True,
                message=message,
                stats=stats,
                context={"log_analyzed": True, "has_errors": error_count > 0},
            )

        except Exception as e:
            return ProcessorResult(success=False, message=f"Log analysis failed: {e}")


# This is optional - if you want to test your plugin standalone
if __name__ == "__main__":
    # Simple test when running the plugin directly
    processor = DocumentProcessor()
    print(f"Plugin: {processor.name} v{processor.version}")
    print(f"Supports: {processor.supported_extensions}")
    print(f"Description: {processor.description}")

    # Test with this file itself
    test_file = Path(__file__)
    if processor.can_process(test_file):
        result = processor.process(test_file, {})
        print(f"Test result: {result.success}")
        print(f"Message: {result.message}")
        if result.stats:
            print("Stats:", result.stats)
    else:
        print("Cannot process test file")
