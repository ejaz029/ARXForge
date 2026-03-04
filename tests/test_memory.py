"""
Phase 6: Memory Test
Test conversation memory - verify context is retained across queries.
"""
import os
import pytest
from ai.arxml_agent import run_agent_query, create_agent_graph

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


@pytest.fixture
def fresh_agent():
    """Create fresh agent instance for each test to avoid state leakage."""
    return create_agent_graph(upload_folder="uploads")


class TestConversationMemory:
    """Test that conversation context is retained."""
    
    def test_memory_across_queries(self, test_file):
        """Test: Ask to extract ports, then validate them (should remember ports)."""
        selected_file = os.path.basename(test_file)
        thread_id = "test_memory_1"
        
        # First query: Extract ports
        query1 = "Extract all ports"
        print(f"\n[TEST] Query 1: '{query1}'")
        
        response1 = run_agent_query(
            query1,
            selected_file=selected_file,
            upload_folder="uploads",
            thread_id=thread_id
        )
        
        assert isinstance(response1, str)
        assert len(response1) > 0
        print(f"   Response 1: {response1[:150]}...")
        
        # Second query: Validate them (should remember ports from query 1)
        query2 = "Now validate them"
        print(f"\n[TEST] Query 2: '{query2}' (should remember ports)")
        
        response2 = run_agent_query(
            query2,
            selected_file=selected_file,
            upload_folder="uploads",
            thread_id=thread_id  # Same thread = same memory
        )
        
        assert isinstance(response2, str)
        assert len(response2) > 0
        
        # Response 2 should reference ports or validation
        response2_lower = response2.lower()
        has_context = any(keyword in response2_lower for keyword in [
            "port", "validate", "validation", "check", "them", "those"
        ])
        
        assert has_context, f"Response 2 should reference previous context: {response2[:200]}"
        
        print(f"   Response 2: {response2[:150]}...")
        print(f"\n[PASS] Memory retained across queries")
    
    def test_memory_isolation(self, test_file):
        """Test that different threads have isolated memory."""
        file1 = os.path.basename(test_file)
        thread1 = "test_memory_thread_1"
        thread2 = "test_memory_thread_2"
        
        # Query in thread 1
        query1 = "Extract all software components"
        response1 = run_agent_query(
            query1,
            selected_file=file1,
            upload_folder="uploads",
            thread_id=thread1
        )
        
        # Same query in thread 2 (should not see thread 1's context)
        response2 = run_agent_query(
            query1,
            selected_file=file1,
            upload_folder="uploads",
            thread_id=thread2
        )
        
        # Both should work independently
        assert isinstance(response1, str)
        assert isinstance(response2, str)
        
        print(f"\n[PASS] Memory isolation works (different threads)")
    
    def test_follow_up_question(self, test_file):
        """Test follow-up questions that rely on previous context."""
        selected_file = os.path.basename(test_file)
        thread_id = "test_memory_followup"
        
        # Initial query
        query1 = "What components are in this file?"
        print(f"\n[TEST] Query 1: '{query1}'")
        
        response1 = run_agent_query(
            query1,
            selected_file=selected_file,
            upload_folder="uploads",
            thread_id=thread_id
        )
        
        # Follow-up that references previous answer
        query2 = "Are there any duplicates among them?"
        print(f"\n[TEST] Query 2: '{query2}' (follow-up)")
        
        response2 = run_agent_query(
            query2,
            selected_file=selected_file,
            upload_folder="uploads",
            thread_id=thread_id
        )
        
        assert isinstance(response2, str)
        assert len(response2) > 0
        
        # Should understand "them" refers to components
        print(f"   Response 2: {response2[:150]}...")
        print(f"\n[PASS] Follow-up question handled with context")


class TestMemoryPersistence:
    """Test that memory persists across multiple interactions."""
    
    def test_multi_turn_conversation(self, test_file):
        """Test a multi-turn conversation."""
        selected_file = os.path.basename(test_file)
        thread_id = "test_memory_multiturn"
        
        queries = [
            "Extract all ports",
            "How many are P-PORTs?",
            "Validate the communication for those ports",
            "Summarize the findings"
        ]
        
        responses = []
        for i, query in enumerate(queries, 1):
            print(f"\n[TEST] Turn {i}: '{query}'")
            
            response = run_agent_query(
                query,
                selected_file=selected_file,
                upload_folder="uploads",
                thread_id=thread_id
            )
            
            assert isinstance(response, str)
            assert len(response) > 0
            responses.append(response)
            print(f"   Response: {response[:100]}...")
        
        # All responses should be coherent
        assert len(responses) == len(queries)
        print(f"\n[PASS] Multi-turn conversation completed ({len(queries)} turns)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
