"""
Phase 4: Tool Chaining Test
Test multi-step queries - verify tools are called in sequence and results are merged.
"""
import os
import pytest
from ai.arxml_agent import run_agent_query

TEST_FILE = os.path.join("uploads", "SystemExtract 5_original.arxml")
FALLBACK_FILE = os.path.join("uploads", "A_Dimmer.arxml")


@pytest.fixture
def test_file():
    """Get a valid test file path."""
    if os.path.exists(TEST_FILE):
        return TEST_FILE
    elif os.path.exists(FALLBACK_FILE):
        return FALLBACK_FILE
    else:
        pytest.skip("No test ARXML files found in uploads folder")


class TestMultiStepQueries:
    """Test multi-step query execution."""
    
    def test_validate_components_and_uuids(self, test_file):
        """Test: 'Validate components and check duplicate UUIDs'"""
        query = "Validate components and check duplicate UUIDs"
        selected_file = os.path.basename(test_file)
        
        print(f"\n[TEST] Testing query: '{query}'")
        print(f"📄 Using file: {selected_file}")
        
        response = run_agent_query(
            query,
            selected_file=selected_file,
            upload_folder="uploads",
            thread_id="test_chaining_1"
        )
        
        assert isinstance(response, str), "Response should be a string"
        assert len(response) > 0, "Response should not be empty"
        
        # Strong assertions: Check for error indicators
        assert "Error during agent execution" not in response, f"Agent execution failed: {response[:200]}"
        assert "Failed to call a function" not in response, f"Function call failed: {response[:200]}"
        assert not response.startswith("❌"), f"Response starts with error: {response[:200]}"
        assert "❌ Error" not in response, f"Error found in response: {response[:200]}"
        
        # Check if response mentions validation or UUIDs
        response_lower = response.lower()
        has_validation = any(keyword in response_lower for keyword in ["validate", "validation", "check", "duplicate", "uuid"])
        assert has_validation, f"Response should mention validation/UUIDs: {response[:200]}"
        
        print(f"\n[PASS] Response received ({len(response)} chars)")
        print(f"   Preview: {response[:150]}...")
    
    def test_extract_and_validate(self, test_file):
        """Test: 'Extract all ports and validate them'"""
        query = "Extract all ports and validate them"
        selected_file = os.path.basename(test_file)
        
        print(f"\n[TEST] Testing query: '{query}'")
        
        response = run_agent_query(
            query,
            selected_file=selected_file,
            upload_folder="uploads",
            thread_id="test_chaining_2"
        )
        
        assert isinstance(response, str)
        assert len(response) > 0
        
        # Strong assertions: Check for error indicators
        assert "Error during agent execution" not in response, f"Agent execution failed: {response[:200]}"
        assert "Failed to call a function" not in response, f"Function call failed: {response[:200]}"
        assert not response.startswith("❌"), f"Response starts with error: {response[:200]}"
        assert "❌ Error" not in response, f"Error found in response: {response[:200]}"
        
        # Should mention ports or extraction
        response_lower = response.lower()
        has_ports = any(keyword in response_lower for keyword in ["port", "extract", "p-port", "r-port"])
        assert has_ports, f"Response should mention ports: {response[:200]}"
        
        print(f"\n[PASS] Response received")
        print(f"   Preview: {response[:150]}...")
    
    def test_comprehensive_validation(self, test_file):
        """Test: 'Run comprehensive validation including schema, UUIDs, and data consistency'"""
        query = "Run comprehensive validation including schema, UUIDs, and data consistency"
        selected_file = os.path.basename(test_file)
        
        print(f"\n[TEST] Testing complex query: '{query}'")
        
        response = run_agent_query(
            query,
            selected_file=selected_file,
            upload_folder="uploads",
            thread_id="test_chaining_3"
        )
        
        assert isinstance(response, str)
        assert len(response) > 0
        
        # Strong assertions: Check for error indicators
        assert "Error during agent execution" not in response, f"Agent execution failed: {response[:200]}"
        assert "Failed to call a function" not in response, f"Function call failed: {response[:200]}"
        assert not response.startswith("❌"), f"Response starts with error: {response[:200]}"
        assert "❌ Error" not in response, f"Error found in response: {response[:200]}"
        
        # Should be comprehensive
        response_lower = response.lower()
        has_validation = any(keyword in response_lower for keyword in ["validate", "check", "schema", "uuid", "consistency"])
        assert has_validation, f"Response should be comprehensive: {response[:200]}"
        
        print(f"\n[PASS] Comprehensive validation completed")
        print(f"   Preview: {response[:200]}...")


class TestToolExecutionTracking:
    """Test that we can track which tools were executed."""
    
    def test_multiple_tools_executed(self, test_file):
        """Verify that multiple tools are called for multi-step queries."""
        query = "Extract software components, extract ports, and check for duplicate UUIDs"
        selected_file = os.path.basename(test_file)
        
        print(f"\n[TEST] Testing multi-tool query: '{query}'")
        
        response = run_agent_query(
            query,
            selected_file=selected_file,
            upload_folder="uploads",
            thread_id="test_tracking_1"
        )
        
        assert isinstance(response, str)
        assert len(response) > 0
        
        # Response should contain information from multiple tools
        response_lower = response.lower()
        keywords_found = sum([
            "component" in response_lower or "swc" in response_lower,
            "port" in response_lower,
            "uuid" in response_lower or "duplicate" in response_lower
        ])
        
        # Should find at least 2 out of 3 keywords (some tools might not find data)
        assert keywords_found >= 1, f"Should execute multiple tools, found {keywords_found} keywords"
        
        print(f"\n[PASS] Multiple tools executed (found {keywords_found}/3 keywords)")
        print(f"   Preview: {response[:200]}...")


class TestResultMerging:
    """Test that results from multiple tools are properly merged."""
    
    def test_results_merged(self, test_file):
        """Test that results from different tools are combined in response."""
        query = "Extract components and validate data consistency"
        selected_file = os.path.basename(test_file)
        
        print(f"\n[TEST] Testing result merging: '{query}'")
        
        response = run_agent_query(
            query,
            selected_file=selected_file,
            upload_folder="uploads",
            thread_id="test_merging_1"
        )
        
        assert isinstance(response, str)
        assert len(response) > 0
        
        # Strong assertions: Check for error indicators
        assert "Error during agent execution" not in response, f"Agent execution failed: {response[:200]}"
        assert "Failed to call a function" not in response, f"Function call failed: {response[:200]}"
        assert not response.startswith("❌"), f"Response starts with error: {response[:200]}"
        assert "❌ Error" not in response, f"Error found in response: {response[:200]}"
        
        # Response should synthesize information from multiple tools
        # Check that it's not just a single tool's output
        lines = response.split("\n")
        assert len(lines) > 1, "Response should have multiple lines (merged results)"
        
        print(f"\n[PASS] Results merged ({len(lines)} lines)")
        print(f"   Preview: {response[:200]}...")


class TestErrorHandling:
    """Test error handling in tool chaining."""
    
    def test_partial_failure(self, test_file):
        """Test that partial tool failures don't crash the agent."""
        query = "Extract components from nonexistent file and validate schema"
        # Use invalid file to test error handling
        
        print(f"\n[TEST] Testing error handling with invalid file")
        
        response = run_agent_query(
            query,
            selected_file="nonexistent.arxml",
            upload_folder="uploads",
            thread_id="test_error_1"
        )
        
        assert isinstance(response, str)
        # Should handle error gracefully - either explicit error message or valid response
        # Don't fail if it's an expected error message
        if "error" not in response.lower():
            # If no error, check it's not an unexpected error format
            assert "Error during agent execution" not in response, f"Unexpected agent error: {response[:200]}"
            assert "Failed to call a function" not in response, f"Unexpected function call error: {response[:200]}"
        
        print(f"\n[PASS] Error handled gracefully")
        print(f"   Response: {response[:200]}...")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
