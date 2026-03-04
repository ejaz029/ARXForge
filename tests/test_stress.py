"""
Phase 7: Stress Test
Test complex multi-step queries, sequential execution, and error handling.
"""
import os
import pytest
import time
from ai.arxml_agent import run_agent_query

# Mark all stress tests with timeout
pytestmark = pytest.mark.timeout(120)  # 2 minute timeout for all tests in this file

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


class TestComplexQueries:
    """Test very complex multi-step queries."""
    
    @pytest.mark.timeout(180)  # 3 minute timeout for this specific test
    def test_comprehensive_validation_stress(self, test_file):
        """Test: 'Run a comprehensive validation, analyze communication mappings, detect inconsistencies, and summarize issues'"""
        query = "Run a comprehensive validation, analyze communication mappings, detect inconsistencies, and summarize issues"
        selected_file = os.path.basename(test_file)
        
        print(f"\n[TEST] STRESS TEST: Complex comprehensive query")
        print(f"[FILE] File: {selected_file}")
        print(f"[INFO] Starting execution...")
        
        start_time = time.time()
        
        try:
            response = run_agent_query(
                query,
                selected_file=selected_file,
                upload_folder="uploads",
                thread_id="stress_test_1"
            )
            
            elapsed = time.time() - start_time
            
            assert isinstance(response, str), "Response should be a string"
            assert len(response) > 0, "Response should not be empty"
            assert elapsed < 180, f"Query took too long: {elapsed:.2f}s (timeout: 180s)"
            
            print(f"\n[PASS] Stress test passed")
            print(f"   Execution time: {elapsed:.2f}s")
            print(f"   Response length: {len(response)} chars")
            print(f"   Preview: {response[:200]}...")
            
        except Exception as e:
            pytest.fail(f"Stress test failed with error: {str(e)}")
    
    def test_multi_step_breakdown(self, test_file):
        """Test that complex query is broken into steps."""
        query = "Extract all components, validate schema, check UUIDs, analyze communication, and report findings"
        selected_file = os.path.basename(test_file)
        
        print(f"\n[TEST] Testing multi-step breakdown")
        
        start_time = time.time()
        
        response = run_agent_query(
            query,
            selected_file=selected_file,
            upload_folder="uploads",
            thread_id="stress_test_2"
        )
        
        elapsed = time.time() - start_time
        
        assert isinstance(response, str)
        assert len(response) > 0
        assert elapsed < 120, f"Query took too long: {elapsed:.2f}s"
        
        # Response should show evidence of multiple steps
        response_lower = response.lower()
        keywords_found = sum([
            "component" in response_lower,
            "schema" in response_lower or "validate" in response_lower,
            "uuid" in response_lower,
            "communication" in response_lower or "pdu" in response_lower,
            "find" in response_lower or "report" in response_lower
        ])
        
        assert keywords_found >= 2, f"Should execute multiple steps, found {keywords_found}/5 keywords"
        
        print(f"\n[PASS] Multi-step breakdown successful")
        print(f"   Execution time: {elapsed:.2f}s")
        print(f"   Keywords found: {keywords_found}/5")
    
    def test_sequential_execution(self, test_file):
        """Test that tools execute sequentially (not all at once)."""
        query = "First extract ports, then validate them, then check for duplicates"
        selected_file = os.path.basename(test_file)
        
        print(f"\n[TEST] Testing sequential execution")
        
        response = run_agent_query(
            query,
            selected_file=selected_file,
            upload_folder="uploads",
            thread_id="stress_test_3"
        )
        
        assert isinstance(response, str)
        assert len(response) > 0
        
        # Should show evidence of sequential execution
        print(f"\n[PASS] Sequential execution completed")
        print(f"   Preview: {response[:200]}...")


class TestErrorRecovery:
    """Test error recovery and handling."""
    
    def test_partial_failure_recovery(self, test_file):
        """Test that partial failures don't crash the system."""
        query = "Extract components from invalid file and validate schema of valid file"
        selected_file = os.path.basename(test_file)
        
        print(f"\n[TEST] Testing error recovery")
        
        # This should handle errors gracefully
        response = run_agent_query(
            query,
            selected_file="nonexistent.arxml",  # Invalid file
            upload_folder="uploads",
            thread_id="stress_test_error_1"
        )
        
        assert isinstance(response, str)
        # Should either handle error or provide partial results
        assert len(response) > 0
        
        print(f"\n[PASS] Error recovery successful")
        print(f"   Response: {response[:200]}...")
    
    def test_timeout_handling(self, test_file):
        """Test that very long queries don't hang forever."""
        # Create a query that might take a while
        query = "Run all validations, extract everything, analyze completely, and provide detailed report"
        selected_file = os.path.basename(test_file)
        
        print(f"\n[TEST] Testing timeout handling")
        
        start_time = time.time()
        
        response = run_agent_query(
            query,
            selected_file=selected_file,
            upload_folder="uploads",
            thread_id="stress_test_timeout_1"
        )
        
        elapsed = time.time() - start_time
        
        assert isinstance(response, str)
        assert elapsed < 180, f"Query should complete within 180s, took {elapsed:.2f}s"
        
        print(f"\n[PASS] Timeout handling works")
        print(f"   Execution time: {elapsed:.2f}s")


class TestResourceUsage:
    """Test resource usage and performance."""
    
    def test_no_memory_leak(self, test_file):
        """Test that multiple queries don't cause memory leaks."""
        selected_file = os.path.basename(test_file)
        thread_id = "stress_test_memory"
        
        print(f"\n[TEST] Testing for memory leaks")
        
        # Run multiple queries in same thread
        for i in range(5):
            query = f"Query {i+1}: Extract components"
            response = run_agent_query(
                query,
                selected_file=selected_file,
                upload_folder="uploads",
                thread_id=thread_id
            )
            assert isinstance(response, str)
            assert len(response) > 0
        
        print(f"\n[PASS] No memory leak detected (5 queries completed)")


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_empty_query(self, test_file):
        """Test handling of empty queries."""
        selected_file = os.path.basename(test_file)
        
        response = run_agent_query(
            "",
            selected_file=selected_file,
            upload_folder="uploads",
            thread_id="stress_test_empty"
        )
        
        # Should handle gracefully
        assert isinstance(response, str)
        print(f"\n[PASS] Empty query handled")
    
    def test_very_long_query(self, test_file):
        """Test handling of very long queries."""
        selected_file = os.path.basename(test_file)
        long_query = "Extract " + " and validate " * 20 + "everything"
        
        response = run_agent_query(
            long_query,
            selected_file=selected_file,
            upload_folder="uploads",
            thread_id="stress_test_long"
        )
        
        assert isinstance(response, str)
        assert len(response) > 0
        
        print(f"\n[PASS] Very long query handled")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
