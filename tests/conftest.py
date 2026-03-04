"""
Pytest configuration and shared fixtures.
"""
import os
import sys
import io
import pytest

# Configure UTF-8 encoding for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        # Fallback for older Python versions
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


@pytest.fixture(scope="session")
def test_files():
    """Get list of available test ARXML/XML files."""
    from app.file_utils import is_arxml_only
    uploads_dir = os.path.join(project_root, "uploads")
    if not os.path.exists(uploads_dir):
        return []
    arxml_files = [f for f in os.listdir(uploads_dir) if is_arxml_only(f)]
    return arxml_files


@pytest.fixture(scope="session")
def uploads_folder():
    """Get uploads folder path."""
    return os.path.join(project_root, "uploads")
