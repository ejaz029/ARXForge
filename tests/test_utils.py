"""
Test utility helpers for consistent tool invocation and mocking.
"""
import sys
import io
import pytest
from typing import Any, Dict
from unittest.mock import patch, MagicMock

# Configure UTF-8 encoding for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        # Fallback for older Python versions
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def run_tool(tool, **kwargs) -> str:
    """
    Unified tool invocation helper.
    
    Handles both LangChain tool.invoke() and direct function calls.
    
    Args:
        tool: LangChain tool instance or callable
        **kwargs: Tool arguments
        
    Returns:
        Tool result as string
    """
    try:
        # Try invoke method (LangChain standard)
        if hasattr(tool, 'invoke'):
            result = tool.invoke(kwargs)
        else:
            # Fallback: call directly as function
            result = tool(**kwargs)
    except (AttributeError, TypeError) as e:
        # If invoke fails, try direct call
        try:
            result = tool(**kwargs)
        except Exception:
            # Last resort: try with single positional arg if only one kwarg
            if len(kwargs) == 1:
                result = tool(list(kwargs.values())[0])
            else:
                raise e
    
    return str(result) if result is not None else ""


def mock_rag_response(query: str, selected_file: str = None, upload_folder: str = "uploads") -> str:
    """
    Mock RAG response for testing.
    
    Args:
        query: User query
        selected_file: Selected ARXML file
        upload_folder: Upload folder path
        
    Returns:
        Mocked RAG response
    """
    response = f"[MOCK RAG] Response to query: {query}"
    if selected_file:
        response += f"\n[MOCK RAG] Using file: {selected_file}"
    return response


@pytest.fixture
def mock_rag():
    """Fixture to mock RAG processing."""
    from unittest.mock import patch
    with patch('ai.rag_validation.process_query_with_rag') as mock:
        def mock_side_effect(query, upload_folder, selected_file=None):
            return mock_rag_response(query, selected_file, upload_folder)
        mock.side_effect = mock_side_effect
        yield mock
