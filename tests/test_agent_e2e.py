"""
End-to-end tests for the ARXML agent.
Runs run_agent_query with real ARXML paths and checks response and conversation memory.
"""
import os
import pytest

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in __import__("sys").path:
    __import__("sys").path.insert(0, project_root)

from ai.arxml_agent import run_agent_query


def _uploads_dir():
    return os.path.join(project_root, "uploads")


def _get_one_arxml():
    from app.file_utils import is_arxml_only
    up = _uploads_dir()
    if not os.path.isdir(up):
        return None
    for f in os.listdir(up):
        if is_arxml_only(f):
            return f
    return None


@pytest.fixture
def upload_folder():
    return _uploads_dir()


@pytest.fixture
def selected_file(upload_folder):
    name = _get_one_arxml()
    if not name:
        pytest.skip("No ARXML files in uploads folder")
    return name


class TestAgentE2E:
    """End-to-end agent tests."""

    def test_run_agent_query_returns_non_empty_response(self, upload_folder, selected_file):
        """Run agent with a real ARXML file and assert non-empty, non-error response."""
        response = run_agent_query(
            user_query="List software components",
            selected_file=selected_file,
            upload_folder=upload_folder,
            thread_id="e2e_single",
        )
        assert isinstance(response, str), "Response should be a string"
        assert len(response.strip()) > 0, "Response should not be empty"
        assert not response.strip().startswith("❌"), "Response should not be an error message"

    def test_run_agent_query_conversation_memory(self, upload_folder, selected_file):
        """Two queries with same thread_id should both succeed (memory preserved)."""
        thread_id = "e2e_memory_test"
        r1 = run_agent_query(
            user_query="What validation checks can you run?",
            selected_file=selected_file,
            upload_folder=upload_folder,
            thread_id=thread_id,
        )
        assert isinstance(r1, str) and len(r1.strip()) > 0
        r2 = run_agent_query(
            user_query="Summarize the previous answer in one sentence.",
            selected_file=selected_file,
            upload_folder=upload_folder,
            thread_id=thread_id,
        )
        assert isinstance(r2, str) and len(r2.strip()) > 0
        assert not r2.strip().startswith("❌"), "Second response should not be an error"
