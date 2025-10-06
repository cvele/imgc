"""
Tests for utility formatting functions.

Tests utility functions used across the imgc package.
"""

import pytest
import sys
from pathlib import Path

# Import the function from where it now lives
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from imgc.plugins.builtin.image_processor import human_readable_size


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

    def test_petabytes(self):
        """Test formatting petabytes."""
        petabyte = 1024 * 1024 * 1024 * 1024 * 1024
        assert human_readable_size(petabyte) == "1.0PB"

    def test_edge_cases(self):
        """Test edge cases and boundary values."""
        # Test exactly at boundaries
        assert human_readable_size(1024) == "1.0KB"
        assert human_readable_size(1024 * 1024) == "1.0MB"
        assert human_readable_size(1024 * 1024 * 1024) == "1.0GB"

        # Test just under boundaries
        assert human_readable_size(1023) == "1023.0B"
        assert human_readable_size(1024 * 1024 - 1) == "1024.0KB"

    def test_fractional_values(self):
        """Test formatting with fractional values."""
        assert human_readable_size(1536) == "1.5KB"  # 1.5 * 1024
        assert human_readable_size(2621440) == "2.5MB"  # 2.5 * 1024 * 1024
