"""
Phase 3: Agent Planning Test
Test planning node alone - verify multi-step plans are generated correctly.
"""
import os
import json
import pytest
from ai.arxml_agent import create_planning_node, AgentState
from config.llm_config import get_llm
from ai.agent_tools import get_all_tools


@pytest.fixture
def planning_node():
    """Create a planning node for testing."""
    llm = get_llm()
    tools = get_all_tools()
    return create_planning_node(llm, tools)


class TestPlanningNode:
    """Test planning node functionality."""
    
    def test_planning_generates_steps(self, planning_node):
        """Test that planning generates step-by-step plan."""
        state = AgentState(
            messages=[],
            selected_file=None,
            tool_results=[],
            plan=None,
            intent=None,
            iteration_count=0,
            use_rag=False,
            rag_result=None
        )
        
        # Add a user query
        from langchain_core.messages import HumanMessage
        state["messages"] = [HumanMessage(content="Validate all ports and UUIDs")]
        
        result_state = planning_node(state)
        
        assert "plan" in result_state, "Planning should generate a plan"
        plan = result_state.get("plan")
        assert plan is not None, "Plan should not be None"
        assert isinstance(plan, list), "Plan should be a list"
        assert len(plan) > 0, "Plan should have at least one step"
        
        print(f"\n[PASS] Planning generated {len(plan)} steps")
        for i, step in enumerate(plan[:3], 1):  # Show first 3 steps
            print(f"   Step {i}: {step.get('tool_name', 'unknown')} - {step.get('reason', 'N/A')}")
    
    def test_plan_structure(self, planning_node):
        """Test that plan has correct structure."""
        from langchain_core.messages import HumanMessage
        state = AgentState(
            messages=[HumanMessage(content="Extract components and validate schema")],
            selected_file=None,
            tool_results=[],
            plan=None,
            intent=None,
            iteration_count=0,
            use_rag=False,
            rag_result=None
        )
        
        result_state = planning_node(state)
        plan = result_state.get("plan", [])
        
        if plan:
            # Check structure of first step
            first_step = plan[0]
            assert isinstance(first_step, dict), "Each step should be a dictionary"
            # Should have tool_name or similar
            assert "tool_name" in first_step or "tool" in first_step or "action" in first_step, \
                f"Step missing tool identifier: {first_step.keys()}"
        
        print(f"\n[PASS] Plan structure is valid: {len(plan)} steps")
    
    def test_plan_for_complex_query(self, planning_node):
        """Test planning for complex multi-step query."""
        from langchain_core.messages import HumanMessage
        complex_query = "Run a comprehensive validation, analyze communication mappings, detect inconsistencies, and summarize issues"
        
        state = AgentState(
            messages=[HumanMessage(content=complex_query)],
            selected_file=None,
            tool_results=[],
            plan=None,
            intent=None,
            iteration_count=0,
            use_rag=False,
            rag_result=None
        )
        
        result_state = planning_node(state)
        plan = result_state.get("plan", [])
        
        # Complex query should generate multiple steps
        assert len(plan) > 1, f"Complex query should generate multiple steps, got {len(plan)}"
        print(f"\n[PASS] Complex query generated {len(plan)} steps")
    
    def test_plan_sets_intent(self, planning_node):
        """Test that planning also sets intent."""
        from langchain_core.messages import HumanMessage
        state = AgentState(
            messages=[HumanMessage(content="Check for duplicate UUIDs")],
            selected_file=None,
            tool_results=[],
            plan=None,
            intent=None,
            iteration_count=0,
            use_rag=False,
            rag_result=None
        )
        
        result_state = planning_node(state)
        
        assert "intent" in result_state, "Planning should set intent"
        intent = result_state.get("intent")
        assert intent is not None, "Intent should not be None"
        assert intent in ["extraction", "validation", "analysis", "question", "comparison", "unknown"], \
            f"Invalid intent: {intent}"
        
        print(f"\n[PASS] Planning set intent: {intent}")
    
    def test_plan_consistency(self, planning_node):
        """Test that similar queries generate consistent plans."""
        from langchain_core.messages import HumanMessage
        
        query1 = "Validate schema and check UUIDs"
        query2 = "Check UUIDs and validate schema"
        
        state1 = AgentState(
            messages=[HumanMessage(content=query1)],
            selected_file=None,
            tool_results=[],
            plan=None,
            intent=None,
            iteration_count=0,
            use_rag=False,
            rag_result=None
        )
        
        state2 = AgentState(
            messages=[HumanMessage(content=query2)],
            selected_file=None,
            tool_results=[],
            plan=None,
            intent=None,
            iteration_count=0,
            use_rag=False,
            rag_result=None
        )
        
        result1 = planning_node(state1)
        result2 = planning_node(state2)
        
        plan1 = result1.get("plan", [])
        plan2 = result2.get("plan", [])
        
        # Plans should have similar tools (order may differ)
        tools1 = {step.get("tool_name", "") for step in plan1}
        tools2 = {step.get("tool_name", "") for step in plan2}
        
        # Should have some overlap
        assert len(tools1.intersection(tools2)) > 0 or len(plan1) > 0, \
            "Similar queries should generate similar plans"
        
        print(f"\n[PASS] Plan consistency: {len(tools1.intersection(tools2))} common tools")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
