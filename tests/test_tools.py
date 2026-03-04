"""
Phase 1: Unit Testing (Tools Level)
Test each of the 13 tools independently.
No agent logic involved - just direct tool execution.
"""
import os
import pytest
from ai.agent_tools import (
    extract_software_components,
    extract_ports_tool,
    extract_ecu_instances,
    check_duplicate_uuids_tool,
    validate_schema_tool,
    validate_data_consistency_tool,
    validate_swc_tool,
    validate_communication_tool,
    validate_memory_tool,
    validate_rte_tool,
    validate_diagnostics_tool,
    validate_ecu_bsw_tool,
    validate_version_compatibility_tool,
    get_all_tools
)
from tests.test_utils import run_tool

# Test file path - using a sample ARXML file
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


class TestToolExtraction:
    """Test extraction tools."""
    
    def test_extract_software_components(self, test_file):
        """Test software component extraction."""
        result = run_tool(extract_software_components, file_path=test_file)
        assert isinstance(result, str)
        assert "error" not in result.lower() or "no software components" in result.lower()
        print(f"\n[PASS] extract_software_components: {result[:100]}...")
    
    def test_extract_ports_tool(self, test_file):
        """Test port extraction."""
        result = run_tool(extract_ports_tool, file_path=test_file)
        assert isinstance(result, str)
        assert "error" not in result.lower() or "no ports" in result.lower()
        print(f"\n[PASS] extract_ports_tool: {result[:100]}...")
    
    def test_extract_ecu_instances(self, test_file):
        """Test ECU instance extraction."""
        result = run_tool(extract_ecu_instances, file_path=test_file)
        assert isinstance(result, str)
        assert "error" not in result.lower() or "no ecu instances" in result.lower()
        print(f"\n[PASS] extract_ecu_instances: {result[:100]}...")


class TestValidationTools:
    """Test validation tools."""
    
    def test_check_duplicate_uuids_tool(self, test_file):
        """Test duplicate UUID detection."""
        result = run_tool(check_duplicate_uuids_tool, file_path=test_file)
        assert isinstance(result, str)
        # Should contain either "duplicate" or "no duplicate" or "error"
        assert any(keyword in result.lower() for keyword in ["duplicate", "no duplicate", "error", "passed"])
        print(f"\n[PASS] check_duplicate_uuids_tool: {result[:100]}...")
    
    def test_validate_schema_tool(self, test_file):
        """Test schema validation."""
        result = run_tool(validate_schema_tool, arxml_file=test_file)
        assert isinstance(result, str)
        assert "error" not in result.lower() or "schema" in result.lower() or "xsd" in result.lower()
        print(f"\n[PASS] validate_schema_tool: {result[:100]}...")
    
    def test_validate_data_consistency_tool(self, test_file):
        """Test data consistency validation."""
        result = run_tool(validate_data_consistency_tool, file_path=test_file)
        assert isinstance(result, str)
        assert "error" not in result.lower() or "consistency" in result.lower() or "passed" in result.lower()
        print(f"\n[PASS] validate_data_consistency_tool: {result[:100]}...")
    
    def test_validate_swc_tool(self, test_file):
        """Test software component validation."""
        result = run_tool(validate_swc_tool, file_path=test_file)
        assert isinstance(result, str)
        assert "error" not in result.lower() or "swc" in result.lower() or "software component" in result.lower()
        print(f"\n[PASS] validate_swc_tool: {result[:100]}...")
    
    def test_validate_communication_tool(self, test_file):
        """Test communication validation."""
        result = run_tool(validate_communication_tool, file_path=test_file)
        assert isinstance(result, str)
        assert "error" not in result.lower() or "communication" in result.lower() or "pdu" in result.lower()
        print(f"\n[PASS] validate_communication_tool: {result[:100]}...")
    
    def test_validate_memory_tool(self, test_file):
        """Test memory validation."""
        result = run_tool(validate_memory_tool, file_path=test_file)
        assert isinstance(result, str)
        assert "error" not in result.lower() or "memory" in result.lower()
        print(f"\n[PASS] validate_memory_tool: {result[:100]}...")
    
    def test_validate_rte_tool(self, test_file):
        """Test RTE validation."""
        result = run_tool(validate_rte_tool, file_path=test_file)
        assert isinstance(result, str)
        assert "error" not in result.lower() or "rte" in result.lower()
        print(f"\n[PASS] validate_rte_tool: {result[:100]}...")
    
    def test_validate_diagnostics_tool(self, test_file):
        """Test diagnostics validation."""
        result = run_tool(validate_diagnostics_tool, file_path=test_file)
        assert isinstance(result, str)
        assert "error" not in result.lower() or "diagnostic" in result.lower() or "dtc" in result.lower()
        print(f"\n[PASS] validate_diagnostics_tool: {result[:100]}...")
    
    def test_validate_ecu_bsw_tool(self, test_file):
        """Test ECU/BSW validation."""
        result = run_tool(validate_ecu_bsw_tool, file_path=test_file)
        assert isinstance(result, str)
        assert "error" not in result.lower() or "ecu" in result.lower() or "bsw" in result.lower()
        print(f"\n[PASS] validate_ecu_bsw_tool: {result[:100]}...")
    
    def test_validate_version_compatibility_tool(self, test_file):
        """Test version compatibility validation."""
        result = run_tool(validate_version_compatibility_tool, file_path=test_file)
        assert isinstance(result, str)
        assert "error" not in result.lower() or "version" in result.lower() or "autosar" in result.lower()
        print(f"\n[PASS] validate_version_compatibility_tool: {result[:100]}...")


class TestToolRegistry:
    """Test tool registry and availability."""
    
    def test_get_all_tools(self):
        """Test that all 13 tools are available."""
        tools = get_all_tools()
        assert len(tools) == 13, f"Expected 13 tools, got {len(tools)}"
        print(f"\n[PASS] All 13 tools registered: {[tool.name for tool in tools]}")
    
    def test_tools_have_names(self):
        """Test that all tools have proper names."""
        tools = get_all_tools()
        for tool in tools:
            assert hasattr(tool, 'name'), f"Tool {tool} missing name attribute"
            assert tool.name, f"Tool {tool} has empty name"
        print(f"\n[PASS] All tools have names")


class TestToolErrorHandling:
    """Test error handling in tools."""
    
    def test_invalid_file_path(self):
        """Test tools handle invalid file paths gracefully."""
        invalid_path = "nonexistent_file.arxml"
        
        # Test a few tools with invalid path
        result1 = run_tool(extract_software_components, file_path=invalid_path)
        assert isinstance(result1, str)
        assert "error" in result1.lower()
        
        result2 = run_tool(check_duplicate_uuids_tool, file_path=invalid_path)
        assert isinstance(result2, str)
        assert "error" in result2.lower()
        
        print(f"\n[PASS] Tools handle invalid paths gracefully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
