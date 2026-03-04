"""
Phase 2: Intent Router Testing
Test classification accuracy, edge cases, and stability.
"""
import pytest
from ai.intent_router import (
    classify_intent,
    get_recommended_tools,
    should_use_rag,
    IntentType
)


class TestIntentClassification:
    """Test basic intent classification."""
    
    def test_validation_intent(self):
        """Test validation queries."""
        queries = [
            "Check for duplicate UUIDs",
            "Validate the schema",
            "Verify data consistency",
            "Test memory usage",
            "Check communication mappings"
        ]
        for query in queries:
            intent = classify_intent(query)
            assert intent == "validation", f"Query '{query}' classified as {intent}, expected 'validation'"
        print("\n[PASS] Validation intent classification works")
    
    def test_extraction_intent(self):
        """Test extraction queries."""
        queries = [
            "Extract all software components",
            "List all ports",
            "Show ECU instances",
            "Get all components",
            "Display ports"
        ]
        for query in queries:
            intent = classify_intent(query)
            assert intent == "extraction", f"Query '{query}' classified as {intent}, expected 'extraction'"
        print("\n[PASS] Extraction intent classification works")
    
    def test_analysis_intent(self):
        """Test analysis queries."""
        queries = [
            "Analyze the ARXML file",
            "Run comprehensive analysis",
            "Examine all components",
            "Review the entire file"
        ]
        for query in queries:
            intent = classify_intent(query)
            assert intent == "analysis", f"Query '{query}' classified as {intent}, expected 'analysis'"
        print("\n[PASS] Analysis intent classification works")
    
    def test_question_intent(self):
        """Test question queries."""
        queries = [
            "What is a software component?",
            "How does AUTOSAR work?",
            "Explain the purpose of SWC",
            "Tell me about ports",
            "What are ECUs?"
        ]
        for query in queries:
            intent = classify_intent(query)
            assert intent == "question", f"Query '{query}' classified as {intent}, expected 'question'"
        print("\n[PASS] Question intent classification works")
    
    def test_comparison_intent(self):
        """Test comparison queries."""
        queries = [
            "Compare file A and file B",
            "What's the difference between these files?",
            "Compare components",
            "Show similarities"
        ]
        for query in queries:
            intent = classify_intent(query)
            assert intent == "comparison", f"Query '{query}' classified as {intent}, expected 'comparison'"
        print("\n[PASS] Comparison intent classification works")


class TestEdgeCases:
    """Test edge cases and ambiguous queries."""
    
    def test_random_question(self):
        """Test random/unrelated questions."""
        queries = [
            "What is the weather?",
            "Hello world",
            "Random text without meaning",
            "123456789"
        ]
        for query in queries:
            intent = classify_intent(query)
            # Should classify as unknown or question
            assert intent in ["unknown", "question"], f"Random query '{query}' classified as {intent}"
        print("\n[PASS] Random questions handled")
    
    def test_mixed_intent(self):
        """Test queries with mixed intents."""
        queries = [
            "Extract components and validate them",
            "Check for errors and show all ports",
            "Analyze and verify consistency"
        ]
        for query in queries:
            intent = classify_intent(query)
            # Should classify as analysis (multi-step)
            assert intent in ["analysis", "validation", "extraction"], \
                f"Mixed query '{query}' classified as {intent}"
        print("\n[PASS] Mixed intent queries handled")
    
    def test_complex_multi_step(self):
        """Test complex multi-step requests."""
        queries = [
            "Run a comprehensive validation, analyze communication mappings, detect inconsistencies, and summarize issues",
            "Validate all components, check ports, verify ECUs, and report findings",
            "Extract everything, validate schema, check consistency, and analyze results"
        ]
        for query in queries:
            intent = classify_intent(query)
            assert intent in ["analysis", "validation"], \
                f"Complex query classified as {intent}, expected analysis or validation"
        print("\n[PASS] Complex multi-step queries classified correctly")
    
    def test_empty_query(self):
        """Test empty or whitespace queries."""
        intent = classify_intent("")
        assert intent in ["unknown", "question"], f"Empty query classified as {intent}"
        
        intent = classify_intent("   ")
        assert intent in ["unknown", "question"], f"Whitespace query classified as {intent}"
        print("\n[PASS] Empty queries handled")


class TestToolRecommendations:
    """Test tool recommendations based on intent."""
    
    def test_validation_tool_recommendations(self):
        """Test tools recommended for validation."""
        tools = get_recommended_tools("validation")
        assert len(tools) > 0, "Validation intent should recommend tools"
        assert "validate_schema_tool" in tools or "check_duplicate_uuids_tool" in tools
        print(f"\n[PASS] Validation tools recommended: {tools}")
    
    def test_extraction_tool_recommendations(self):
        """Test tools recommended for extraction."""
        tools = get_recommended_tools("extraction")
        assert len(tools) > 0, "Extraction intent should recommend tools"
        assert any("extract" in tool for tool in tools)
        print(f"\n[PASS] Extraction tools recommended: {tools}")
    
    def test_question_no_tools(self):
        """Test that questions don't recommend tools (use RAG)."""
        tools = get_recommended_tools("question")
        assert len(tools) == 0, "Question intent should not recommend tools (uses RAG)"
        print("\n[PASS] Questions correctly use RAG (no tools)")


class TestRAGDecision:
    """Test RAG usage decision logic."""
    
    def test_rag_for_questions(self):
        """Test that questions use RAG."""
        assert should_use_rag("question") == True
        print("\n[PASS] Questions trigger RAG")
    
    def test_rag_for_unknown(self):
        """Test that unknown intents use RAG."""
        assert should_use_rag("unknown") == True
        print("\n[PASS] Unknown intents trigger RAG")
    
    def test_no_rag_for_validation(self):
        """Test that validation doesn't use RAG."""
        assert should_use_rag("validation") == False
        print("\n[PASS] Validation doesn't trigger RAG")
    
    def test_no_rag_for_extraction(self):
        """Test that extraction doesn't use RAG."""
        assert should_use_rag("extraction") == False
        print("\n[PASS] Extraction doesn't trigger RAG")


class TestStability:
    """Test router stability and determinism."""
    
    def test_deterministic_classification(self):
        """Test that same query gives same result."""
        query = "Check for duplicate UUIDs"
        results = [classify_intent(query) for _ in range(5)]
        # All results should be the same
        assert len(set(results)) == 1, f"Classification not deterministic: {results}"
        print("\n[PASS] Classification is deterministic")
    
    def test_case_insensitive(self):
        """Test that case doesn't affect classification."""
        query1 = "CHECK FOR DUPLICATE UUIDs"
        query2 = "check for duplicate uuids"
        query3 = "Check For Duplicate Uuids"
        
        intent1 = classify_intent(query1)
        intent2 = classify_intent(query2)
        intent3 = classify_intent(query3)
        
        assert intent1 == intent2 == intent3, \
            f"Case sensitivity issue: {intent1} != {intent2} != {intent3}"
        print("\n[PASS] Classification is case-insensitive")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
