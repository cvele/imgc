"""Tests for main.py argument parsing and path validation."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from main import main


def test_process_existing_argument_parsing(monkeypatch, tmp_path):
    """Test that --process-existing flag is parsed correctly."""
    
    # Mock start_watch to capture arguments
    start_watch_calls = []
    
    def mock_start_watch(*args, **kwargs):
        start_watch_calls.append(kwargs)
    
    monkeypatch.setattr('main.start_watch', mock_start_watch)
    monkeypatch.setattr('main.configure_logging', lambda *args: None)
    
    # Test with --process-existing flag
    test_args = ['--root', str(tmp_path), '--process-existing']
    monkeypatch.setattr('sys.argv', ['main.py'] + test_args)
    
    main()
    
    assert len(start_watch_calls) == 1
    assert start_watch_calls[0]['process_existing'] is True


def test_process_existing_default_false(monkeypatch, tmp_path):
    """Test that process_existing defaults to False."""
    
    # Mock start_watch to capture arguments
    start_watch_calls = []
    
    def mock_start_watch(*args, **kwargs):
        start_watch_calls.append(kwargs)
    
    monkeypatch.setattr('main.start_watch', mock_start_watch)
    monkeypatch.setattr('main.configure_logging', lambda *args: None)
    
    # Test without --process-existing flag
    test_args = ['--root', str(tmp_path)]
    monkeypatch.setattr('sys.argv', ['main.py'] + test_args)
    
    main()
    
    assert len(start_watch_calls) == 1
    assert start_watch_calls[0]['process_existing'] is False


def test_environment_variable_process_existing_integration(monkeypatch, tmp_path):
    """Test that IMGC_PROCESS_EXISTING environment variable works end-to-end."""
    
    # Mock start_watch to capture arguments
    start_watch_calls = []
    
    def mock_start_watch(*args, **kwargs):
        start_watch_calls.append(kwargs)
    
    monkeypatch.setattr('main.start_watch', mock_start_watch)
    monkeypatch.setattr('main.configure_logging', lambda *args: None)
    
    # Test with environment variable set to true
    monkeypatch.setenv('IMGC_PROCESS_EXISTING', 'true')
    test_args = ['--root', str(tmp_path)]
    monkeypatch.setattr('sys.argv', ['main.py'] + test_args)
    
    main()
    
    assert len(start_watch_calls) == 1
    assert start_watch_calls[0]['process_existing'] is True


def test_command_line_overrides_environment(monkeypatch, tmp_path):
    """Test that command line flag overrides environment variable."""
    
    # Mock start_watch to capture arguments
    start_watch_calls = []
    
    def mock_start_watch(*args, **kwargs):
        start_watch_calls.append(kwargs)
    
    monkeypatch.setattr('main.start_watch', mock_start_watch)
    monkeypatch.setattr('main.configure_logging', lambda *args: None)
    
    # Set environment to false, but use command line flag (should be True)
    monkeypatch.setenv('IMGC_PROCESS_EXISTING', 'false')
    test_args = ['--root', str(tmp_path), '--process-existing']
    monkeypatch.setattr('sys.argv', ['main.py'] + test_args)
    
    main()
    
    assert len(start_watch_calls) == 1
    assert start_watch_calls[0]['process_existing'] is True


def test_path_validation_nonexistent_directory(monkeypatch, capsys):
    """Test error handling for nonexistent directory."""
    
    monkeypatch.setattr('main.configure_logging', lambda *args: None)
    
    nonexistent_path = '/this/path/does/not/exist'
    test_args = ['--root', nonexistent_path]
    monkeypatch.setattr('sys.argv', ['main.py'] + test_args)
    
    with pytest.raises(SystemExit) as exc_info:
        main()
    
    assert exc_info.value.code == 2  # argparse error code
    captured = capsys.readouterr()
    assert 'Root directory does not exist' in captured.err


def test_path_validation_file_not_directory(monkeypatch, capsys, tmp_path):
    """Test error handling when path points to a file instead of directory."""
    
    monkeypatch.setattr('main.configure_logging', lambda *args: None)
    
    # Create a file instead of directory
    test_file = tmp_path / 'not_a_directory.txt'
    test_file.write_text('test content')
    
    test_args = ['--root', str(test_file)]
    monkeypatch.setattr('sys.argv', ['main.py'] + test_args)
    
    with pytest.raises(SystemExit) as exc_info:
        main()
    
    assert exc_info.value.code == 2  # argparse error code
    captured = capsys.readouterr()
    assert 'Root path is not a directory' in captured.err


def test_path_normalization_trailing_slash(monkeypatch, tmp_path):
    """Test that paths with trailing slashes are normalized correctly."""
    
    # Mock start_watch to capture the path argument
    start_watch_calls = []
    
    def mock_start_watch(root_path, *args, **kwargs):
        start_watch_calls.append(root_path)
    
    monkeypatch.setattr('main.start_watch', mock_start_watch)
    monkeypatch.setattr('main.configure_logging', lambda *args: None)
    
    # Test with trailing slash
    path_with_slash = str(tmp_path) + '/'
    test_args = ['--root', path_with_slash]
    monkeypatch.setattr('sys.argv', ['main.py'] + test_args)
    
    main()
    
    assert len(start_watch_calls) == 1
    # Path should be normalized (resolved)
    assert start_watch_calls[0] == tmp_path.resolve()


def test_missing_root_argument(monkeypatch, capsys):
    """Test error handling when no root directory is provided."""
    
    monkeypatch.setattr('main.configure_logging', lambda *args: None)
    
    # No IMGC_ROOT environment variable, no --root argument
    monkeypatch.delenv('IMGC_ROOT', raising=False)
    test_args = []
    monkeypatch.setattr('sys.argv', ['main.py'] + test_args)
    
    with pytest.raises(SystemExit) as exc_info:
        main()
    
    assert exc_info.value.code == 2  # argparse error code
    captured = capsys.readouterr()
    assert 'Root directory not provided' in captured.err
