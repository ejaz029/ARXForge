"""
LangGraph-based AI Agent for autonomous ARXML validation and analysis.
Implements planning, tool selection, intent routing, memory, and RAG fallback.
"""
import os
import json
import logging
from typing import TypedDict, List, Optional, Annotated, Literal
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, END
# Removed ToolNode - using manual tool execution instead
from langgraph.checkpoint.memory import MemorySaver

from config.llm_config import get_llm
from ai.agent_tools import get_all_tools, TOOL_REGISTRY
from ai.intent_router import classify_intent, get_recommended_tools, should_use_rag

# Max tool execution loops (plan → tools → decide_next → tools → ...)
MAX_ITERATIONS = 5

# Shared checkpointer so conversation memory persists across requests (same process).
_shared_checkpointer = None


def _build_deterministic_audit_sections(factual_lines: List[str]) -> dict:
    """
    Build Validation Errors, UUID Consistency, Risk Assessment, and Recommendations
    from factual_lines so the audit report cannot contradict tool results.
    """
    validation_errors: List[str] = []
    risk_high: List[str] = []
    risk_medium: List[str] = []
    risk_low: List[str] = []
    recommendations: List[str] = []
    uuid_line: Optional[str] = None

    for line in factual_lines:
        if line.startswith("UUID:"):
            uuid_line = line
            if "No duplicate UUIDs found" in line:
                continue  # not an error, do not add to validation_errors or recommendations
            if "Duplicate UUIDs found" in line:
                validation_errors.append("Duplicate UUIDs found.")
                risk_low.append("Duplicate UUIDs (reported by check_duplicate_uuids_tool).")
                recommendations.append("Resolve duplicate UUIDs.")
            continue
        if line.startswith("Ports/Interfaces:"):
            if "Missing/broken interface definitions present" in line:
                validation_errors.append("Missing/broken interface definitions (validate_port_references_tool).")
                risk_high.append("Missing/broken interface definitions (port references).")
                recommendations.append("Fix missing/broken interface definitions.")
            continue
        if line.startswith("Components:"):
            if "Undefined software component references present" in line:
                validation_errors.append("Undefined software component references (e.g. CompB).")
                risk_high.append("Undefined software component (e.g. CompB).")
                recommendations.append("Define missing software component (e.g. CompB).")
            continue
        if line.startswith("Ports:"):
            if "Duplicate ports found" in line:
                validation_errors.append("Duplicate ports found.")
                risk_low.append("Duplicate ports (reported by duplicate_ports_tool).")
                recommendations.append("Resolve duplicate ports.")
            continue
        if line.startswith("Version:"):
            if "Unsupported" in line:
                validation_errors.append("Unsupported AUTOSAR version.")
                risk_medium.append("Unsupported AUTOSAR version.")
                recommendations.append("Update AUTOSAR version to a supported one.")
            continue
        if line.startswith("BSW:"):
            if "Required BSW modules missing" in line:
                validation_errors.append("Missing required BSW modules.")
                risk_medium.append("Missing required BSW modules (e.g. COM, DEM, DIO, CAN, LIN).")
                recommendations.append("Add missing BSW modules (e.g. COM, DEM, DIO, CAN, LIN).")
            continue
        if line.startswith("Communication:"):
            if "reported issues" in line:
                validation_errors.append("Communication validation reported issues.")
                risk_medium.append("Communication validation issues.")
                recommendations.append("Fix communication configuration.")

    if uuid_line and "No duplicate UUIDs found" in uuid_line:
        uuid_consistency = "No duplicate UUIDs were found."
    elif uuid_line and "Duplicate UUIDs found" in uuid_line:
        uuid_consistency = "Duplicate UUIDs were found."
    else:
        uuid_consistency = "UUID consistency was not determined (check_duplicate_uuids_tool may not have run)."

    risk_assessment: List[str] = []
    if risk_high:
        risk_assessment.append("High risk: " + "; ".join(risk_high))
    if risk_medium:
        risk_assessment.append("Medium risk: " + "; ".join(risk_medium))
    if risk_low:
        risk_assessment.append("Low risk: " + "; ".join(risk_low))
    if not risk_assessment:
        risk_assessment.append("No risks identified from tool results.")

    return {
        "validation_errors": validation_errors,
        "uuid_consistency": uuid_consistency,
        "risk_assessment": risk_assessment,
        "recommendations": recommendations,
    }


def get_shared_checkpointer():
    """Return a single shared MemorySaver so thread_id-based history is preserved."""
    global _shared_checkpointer
    if _shared_checkpointer is None:
        _shared_checkpointer = MemorySaver()
    return _shared_checkpointer


class AgentState(TypedDict):
    """State schema for the LangGraph agent with memory and planning."""
    messages: Annotated[List[BaseMessage], "add_messages"]
    selected_file: Optional[str]
    tool_results: List[dict]
    plan: Optional[List[str]]
    intent: Optional[str]
    iteration_count: int
    use_rag: bool
    rag_result: Optional[str]


def create_planning_node(llm, tools, selected_file: Optional[str] = None):
    """Create a planning node that generates a step-by-step plan."""
    def planning_node(state: AgentState) -> AgentState:
        """Generate a plan based on user query and intent."""
        messages = state["messages"]
        # Use latest user message for multi-turn context
        user_query = ""
        for m in reversed(messages):
            if isinstance(m, HumanMessage):
                user_query = m.content if hasattr(m, "content") else str(m)
                break
        
        # Classify intent
        intent = classify_intent(user_query)
        recommended_tools = get_recommended_tools(intent)
        
        # Generate plan using LLM
        planning_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a planning agent for ARXML validation. 
Analyze the user's query and create a step-by-step plan using available tools.

Available tools:
- extract_software_components: Extract software components
- extract_ports_tool: Extract ports
- extract_ecu_instances: Extract ECU instances
- extract_uuids_tool: List all UUIDs in the file
- check_duplicate_uuids_tool: Check duplicate UUIDs
- validate_schema_tool: Validate schema
- validate_data_consistency_tool: Validate data consistency
- validate_port_references_tool: Check if port interface references are properly defined
- validate_swc_tool: Validate software components
- validate_communication_tool: Validate communication
- validate_memory_tool: Validate memory
- validate_rte_tool: Validate RTE
- validate_diagnostics_tool: Validate diagnostics
- validate_ecu_bsw_tool: Validate ECU/BSW
- validate_version_compatibility_tool: Check version compatibility
- validate_component_refs_tool: Check that component references point to defined SWC types
- duplicate_ports_tool: Check for duplicate ports (same name+interface more than once)

Create a JSON plan with steps. Each step should specify:
- tool_name: Name of tool to use
- reason: Why this tool is needed
- expected_output: What information this will provide

For full/comprehensive analysis or critical-issues-only requests, include at least: extract_software_components and/or extract_ports_tool, validate_data_consistency_tool, validate_port_references_tool, check_duplicate_uuids_tool, validate_version_compatibility_tool, and other validate_* tools as appropriate.

For requests that mention checking communication mappings or reporting inconsistencies, the plan must include: extract_software_components and/or extract_ports_tool, validate_data_consistency_tool, validate_port_references_tool, validate_communication_tool, and validate_component_refs_tool.

When the user asks which items are duplicated (e.g. "which of them are duplicated?" after discussing ports), use duplicate_ports_tool and optionally check_duplicate_uuids_tool to answer.

Respond with ONLY a JSON array of steps, no other text."""),
            ("human", f"User query: {user_query}\n\nRecommended tools: {', '.join(recommended_tools) if recommended_tools else 'None'}")
        ])
        
        try:
            chain = planning_prompt | llm
            response = chain.invoke({"query": user_query})
            plan_text = response.content.strip()
            
            # Try to parse JSON plan
            if plan_text.startswith("```json"):
                plan_text = plan_text.replace("```json", "").replace("```", "").strip()
            elif plan_text.startswith("```"):
                plan_text = plan_text.replace("```", "").strip()
            
            plan = json.loads(plan_text) if plan_text.startswith("[") else []
        except Exception:
            plan = []
        # Fallback: create simple plan from recommended tools if LLM returned nothing/invalid
        if not plan and recommended_tools:
            if intent == "validation" and "duplicate" in user_query.lower():
                dup_tools = ["duplicate_ports_tool", "check_duplicate_uuids_tool"]
                plan = [
                    {"tool_name": t, "reason": "User asked about duplicates"}
                    for t in dup_tools if t in TOOL_REGISTRY
                ]
            if not plan and intent == "analysis":
                q_lower = user_query.lower()
                critical_or_report = (
                    any(x in q_lower for x in ("critical", "issues", "problems", "what's wrong"))
                    or any(x in q_lower for x in ("structured report", "engineering report", "comprehensive validation"))
                )
                if critical_or_report:
                    critical_tools = [
                        "validate_data_consistency_tool",
                        "validate_port_references_tool",
                        "validate_component_refs_tool",
                        "check_duplicate_uuids_tool",
                        "validate_version_compatibility_tool",
                    ]
                    plan = [
                        {"tool_name": t, "reason": "Validation and consistency checks for report"}
                        for t in critical_tools if t in TOOL_REGISTRY
                    ]
            if not plan:
                fallback_len = 8 if intent == "analysis" else 3
                plan = [{"tool_name": tool, "reason": "Recommended for this intent"}
                       for tool in recommended_tools[:fallback_len]]
        # Validate: filter to steps whose tool_name exists in TOOL_REGISTRY
        valid_plan = []
        for step in (plan or []):
            tool_name = step.get("tool_name", "")
            if tool_name and tool_name in TOOL_REGISTRY:
                valid_plan.append(step)
        # For structured/engineering report requests, ensure critical validators always run (even if LLM plan omitted them)
        q_lower = (user_query or "").lower()
        report_requested = any(
            x in q_lower for x in (
                "structured report", "engineering report", "comprehensive validation",
                "structured engineering report", "generate a report", "generate a structured",
                "complete audit", "full audit", "run an audit", "enterprise audit",
                "enterprise-level", "enterprise level"
            )
        )
        if intent == "analysis" and report_requested:
            critical_tools = [
                "validate_data_consistency_tool",
                "validate_port_references_tool",
                "validate_component_refs_tool",
                "check_duplicate_uuids_tool",
                "validate_version_compatibility_tool",
            ]
            in_plan = {s.get("tool_name") for s in valid_plan}
            for t in critical_tools:
                if t in TOOL_REGISTRY and t not in in_plan:
                    valid_plan.append({"tool_name": t, "reason": "Required for engineering report"})
                    in_plan.add(t)

        return {
            "plan": valid_plan,
            "intent": intent,
            "use_rag": should_use_rag(intent)
        }
    
    return planning_node


def create_tool_execution_node(selected_file: Optional[str] = None, upload_folder: str = "uploads"):
    """Create a node that manually executes tools from the plan."""
    # Build file path if selected_file is provided
    file_path = None
    if selected_file:
        file_path = os.path.join(upload_folder, selected_file)
        if not os.path.exists(file_path):
            file_path = selected_file
    
    def tool_execution_node(state: AgentState) -> AgentState:
        """Manually execute tools from the plan - Python executes, not LLM."""
        plan = state.get("plan", [])
        tool_results = state.get("tool_results", [])
        
        if not plan:
            return {"tool_results": tool_results}
        
        # Execute each tool in the plan
        for step in plan:
            tool_name = step.get("tool_name", "")
            if not tool_name:
                continue
            
            # Get tool from registry
            tool = TOOL_REGISTRY.get(tool_name)
            if not tool:
                tool_results.append({
                    "tool_name": tool_name,
                    "result": f"❌ Tool not found: {tool_name}",
                    "error": True
                })
                continue
            
            # Prepare tool arguments
            args = {}
            
            # Normalize file path
            if file_path:
                normalized_path = os.path.normpath(file_path)
                
                # Check tool schema for argument names
                try:
                    schema_props = tool.args_schema.schema().get("properties", {})
                    
                    # Most tools use "file_path"
                    if "file_path" in schema_props:
                        args["file_path"] = normalized_path
                    # validate_schema_tool uses "arxml_file"
                    elif "arxml_file" in schema_props:
                        args["arxml_file"] = normalized_path
                    else:
                        # Fallback: try file_path anyway
                        args["file_path"] = normalized_path
                except Exception:
                    # If schema check fails, use file_path as default
                    args["file_path"] = normalized_path
            
            # Add xsd_file for schema validation
            if tool_name == "validate_schema_tool":
                xsd_path = os.path.normpath(os.path.join(upload_folder, "AUTOSAR_schema.xsd"))
                if not os.path.exists(xsd_path):
                    xsd_path = os.path.normpath("AUTOSAR_schema.xsd")
                args["xsd_file"] = xsd_path
            
            # Execute tool
            try:
                result = tool.invoke(args)
                tool_results.append({
                    "tool_name": tool_name,
                    "result": str(result) if result else "",
                    "error": False
                })
            except Exception as e:
                tool_results.append({
                    "tool_name": tool_name,
                    "result": f"❌ Error executing {tool_name}: {str(e)}",
                    "error": True
                })
        
        return {
            "tool_results": tool_results,
            "iteration_count": state["iteration_count"] + 1
        }
    
    return tool_execution_node


def create_decide_next_node(llm):
    """Create a node that optionally adds more tool steps based on current results (iterative execution)."""
    def decide_next_node(state: AgentState) -> AgentState:
        iteration_count = state.get("iteration_count", 0)
        if iteration_count >= MAX_ITERATIONS:
            return {"plan": []}
        tool_results = state.get("tool_results", [])
        messages = state["messages"]
        user_query = ""
        for m in reversed(messages):
            if isinstance(m, HumanMessage):
                user_query = m.content if hasattr(m, "content") else str(m)
                break
        results_preview = "\n".join(
            f"- {r.get('tool_name', '?')}: {str(r.get('result', ''))[:200]}"
            for r in tool_results[-5:]
        )
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an ARXML validation agent. Given the user query and the tool results so far, decide if more tools need to run.
Reply with ONLY a JSON array of steps. Each step: {"tool_name": "<name>", "reason": "<why>"}.
Use only these tool names: extract_software_components, extract_ports_tool, extract_ecu_instances, extract_uuids_tool, check_duplicate_uuids_tool, duplicate_ports_tool, validate_schema_tool, validate_data_consistency_tool, validate_port_references_tool, validate_component_refs_tool, validate_swc_tool, validate_communication_tool, validate_memory_tool, validate_rte_tool, validate_diagnostics_tool, validate_ecu_bsw_tool, validate_version_compatibility_tool.
If no more tools are needed, reply with: []"""),
            ("human", f"User query: {user_query}\n\nResults so far:\n{results_preview}\n\nJSON array of additional steps or []:")
        ])
        try:
            chain = prompt | llm
            response = chain.invoke({})
            plan_text = (response.content or "").strip()
            if plan_text.startswith("```"):
                plan_text = plan_text.split("```")[1]
                if plan_text.startswith("json"):
                    plan_text = plan_text[4:].strip()
            plan = json.loads(plan_text) if plan_text.startswith("[") else []
        except Exception:
            plan = []
        valid_plan = [s for s in (plan or []) if s.get("tool_name") in TOOL_REGISTRY]
        return {"plan": valid_plan}
    return decide_next_node


def should_continue_after_tools(state: AgentState) -> Literal["summary", "tools"]:
    """Route to summary or another round of tools (up to MAX_ITERATIONS)."""
    iteration_count = state.get("iteration_count", 0)
    plan = state.get("plan", [])
    if iteration_count >= MAX_ITERATIONS or not plan:
        return "summary"
    return "tools"


def create_summary_node(llm, selected_file: Optional[str] = None):
    """Create a node that uses LLM only to summarize tool results."""
    def summary_node(state: AgentState) -> AgentState:
        """LLM summarizes tool results - NO tool calling here."""
        messages = state["messages"]
        # Use latest user message for multi-turn context
        user_query = ""
        for m in reversed(messages):
            if isinstance(m, HumanMessage):
                user_query = m.content if hasattr(m, "content") else str(m)
                break
        tool_results = state.get("tool_results", [])
        plan = state.get("plan", [])
        
        # Build summary prompt
        summary_content = f"""You are an expert AUTOSAR ARXML validation analyst. Summarize the tool execution results into a comprehensive answer.

User Query: {user_query}

Execution Plan:
"""
        if plan:
            for i, step in enumerate(plan, 1):
                tool_name = step.get("tool_name", "unknown")
                reason = step.get("reason", "")
                summary_content += f"{i}. {tool_name} - {reason}\n"
        elif tool_results:
            for i, result in enumerate(tool_results, 1):
                tool_name = result.get("tool_name", "unknown")
                summary_content += f"{i}. {tool_name} - (executed)\n"

        summary_content += "\nTool Results:\n"
        for i, result in enumerate(tool_results, 1):
            tool_name = result.get("tool_name", "unknown")
            result_text = result.get("result", "")
            error = result.get("error", False)
            # Use higher limit for validation/check tools so critical issues are not cut off
            is_validation = (
                "validate_" in tool_name
                or tool_name == "check_duplicate_uuids_tool"
                or tool_name == "duplicate_ports_tool"
            )
            if tool_name in ("validate_port_references_tool", "validate_component_refs_tool"):
                has_errors = (
                    "❌" in result_text or "not found" in result_text or "Broken" in result_text
                    or "Undefined" in result_text or "required interfaces missing: Yes" in result_text
                )
                truncate_limit = 8000 if has_errors else 6000
            else:
                truncate_limit = 3000 if is_validation else 500
            if not error and len(result_text) > truncate_limit:
                result_text = result_text[:truncate_limit] + "... (truncated)"
            result_text_escaped = result_text.replace("{", "{{").replace("}", "}}")
            summary_content += f"\n{i}. {tool_name}:\n"
            summary_content += f"   Error: {result_text_escaped}\n" if error else f"   {result_text_escaped}\n"

        # Build deterministic factual outcomes from tool_results for critical tools.
        factual_lines: list[str] = []
        for r in tool_results:
            tname = r.get("tool_name", "")
            text = (r.get("result") or "")
            if tname == "check_duplicate_uuids_tool":
                # Only treat as "duplicate UUIDs found" when the tool explicitly returned the failure line (❌ Duplicate UUIDs found).
                # Success is "✅ No duplicate UUIDs found" - any other case we default to no duplicates to avoid false positives.
                if "No duplicate UUIDs found" in text:
                    factual_lines.append("UUID: No duplicate UUIDs found.")
                elif "❌" in text and "Duplicate UUIDs found" in text:
                    factual_lines.append("UUID: Duplicate UUIDs found.")
                else:
                    # Tool error or unknown: do not report duplicates (safe default)
                    factual_lines.append("UUID: No duplicate UUIDs found.")
            elif tname == "validate_port_references_tool":
                # Match all known failure indicators from the tool output
                port_ref_failed = (
                    "Required interfaces missing: Yes." in text
                    or "Not all referenced ports are properly defined" in text
                    or "Broken port references" in text
                    or "broken reference" in text.lower()
                    or ("❌" in text and "required interfaces missing" in text.lower())
                )
                if port_ref_failed:
                    factual_lines.append(
                        "Ports/Interfaces: Missing/broken interface definitions present "
                        "(see validate_port_references_tool)."
                    )
                elif (
                    "Required interfaces missing: No." in text
                    and "All referenced ports are properly defined." in text
                ):
                    factual_lines.append(
                        "Ports/Interfaces: All port interface references are valid."
                    )
            elif tname == "validate_component_refs_tool":
                if "All component references are defined" in text:
                    factual_lines.append("Components: All component references defined.")
                elif (
                    "Undefined component reference" in text
                    or "Undefined component reference(s)" in text
                    or ("❌" in text and "undefined" in text.lower() and "component" in text.lower())
                ):
                    factual_lines.append(
                        "Components: Undefined software component references present "
                        "(see validate_component_refs_tool, e.g. CompB)."
                    )
            elif tname == "duplicate_ports_tool":
                if "No duplicate ports found" in text:
                    factual_lines.append("Ports: No duplicate ports found.")
                elif "duplicate port" in text.lower() or "Duplicate ports" in text:
                    factual_lines.append("Ports: Duplicate ports found.")
            elif tname == "validate_version_compatibility_tool":
                if "unsupported" in text.lower():
                    factual_lines.append("Version: Unsupported AUTOSAR version in this file.")
                elif "supported" in text.lower():
                    factual_lines.append("Version: AUTOSAR version is supported.")
            elif tname == "validate_ecu_bsw_tool":
                if "Missing required BSW module" in text or "missing required BSW" in text:
                    factual_lines.append("BSW: Required BSW modules missing.")
                elif "All required BSW modules are present" in text:
                    factual_lines.append("BSW: All required BSW modules are present.")
            elif tname == "validate_communication_tool":
                if "validation passed" in text or "no communication issues" in text:
                    factual_lines.append("Communication: Communication validation passed.")
                elif "❌" in text or "failed" in text.lower():
                    factual_lines.append("Communication: Communication validation reported issues.")
        if factual_lines:
            summary_content += (
                "\nFACTUAL RESULTS (do not contradict these):\n"
                + "\n".join(f"- {line}" for line in factual_lines)
                + "\n"
            )

        if selected_file:
            summary_content += f"\nNote: Analysis was performed on file '{selected_file}'.\n"
        # REPORT MAPPING RULES (how to use FACTUAL RESULTS in sections):
        # - Validation Errors: include every non-OK factual line (containing missing/undefined/duplicate/unsupported/issues).
        # - UUID Consistency: paraphrase ONLY the UUID factual line; do not invent duplicates when it says no duplicates.
        # - Risk Assessment: prioritize high risk for missing/undefined interfaces/CompB, medium for version/BSW, lower for duplicates.
        # - Final Verdict: must reflect the overall set of failures; if interfaces/CompB fail, the file is incomplete/broken regardless of UUIDs.
        query_lower = user_query.lower()
        critical_issues_requested = any(
            phrase in query_lower for phrase in (
                "critical issue", "critical issues", "issues only", "summarize critical",
                "critical only", "list critical", "critical problems"
            )
        )
        validation_report_requested = any(
            phrase in query_lower for phrase in (
                "comprehensive validation", "structured report", "engineering report",
                "validation report", "full validation", "structured engineering report",
                "complete audit", "full audit", "run an audit", "enterprise audit",
                "enterprise-level", "enterprise level"
            )
        )
        mandatory_failures_block = ""
        if validation_report_requested:
            mandatory_items = []
            for r in tool_results:
                tool_name = r.get("tool_name", "")
                result_text = (r.get("result") or "")
                if tool_name == "validate_port_references_tool":
                    if any(x in result_text for x in ("❌", "Broken", "interface not found", "required interfaces missing: Yes")):
                        mandatory_items.append("Missing/broken interface definitions (from validate_port_references_tool): the tool reported broken port references — list them under Failures/Issues.")
                elif tool_name == "validate_component_refs_tool":
                    if any(x in result_text for x in ("❌", "Undefined", "type missing")):
                        mandatory_items.append("Undefined software component (from validate_component_refs_tool): the tool reported undefined component reference(s) — list under Failures/Issues.")
            if mandatory_items:
                mandatory_failures_block = "\nMANDATORY – Include the following in the Failures/Issues section. Do not omit them:\n" + "\n".join("- " + it for it in mandatory_items) + "\n"
                summary_content += mandatory_failures_block
        enterprise_section_keywords = [
            "structural summary", "validation errors", "communication analysis",
            "uuid consistency", "risk assessment", "final verdict"
        ]
        enterprise_format_requested = sum(1 for k in enterprise_section_keywords if k in query_lower) >= 2
        if enterprise_format_requested:
            summary_content += (
                "\n\nOUTPUT FORMAT (use these section headings in order):\n"
                "1. Structural Summary – SWCs, packages, ports, data types from tool results.\n"
                "2. Validation Errors – All tool-reported failures (port refs, component refs, BSW, version, duplicates, etc.). "
                "Do not state a check passed if the tool reported errors.\n"
                "3. Communication Analysis – From validate_communication_tool and any extract results (signals, frames, clusters).\n"
                "4. UUID Consistency – From check_duplicate_uuids_tool and extract_uuids_tool (unique vs duplicates).\n"
                "5. Risk Assessment – Prioritized risks (e.g. missing interfaces/CompB = high, version/BSW = medium, duplicates = as reported).\n"
                "6. Final Verdict – One short paragraph: compliant / incomplete / broken, and what must be fixed.\n"
                "7. Recommendations – Bullet list of concrete fixes from tool results only.\n"
            )

        # Functional deterministic report: build critical sections from factual_lines so the report cannot contradict tools.
        if (enterprise_format_requested or validation_report_requested) and factual_lines:
            det = _build_deterministic_audit_sections(factual_lines)
            structural_parts: List[str] = []
            for r in tool_results:
                tname = r.get("tool_name", "")
                res = (r.get("result") or "").strip()
                if not res:
                    continue
                first_line = res.split("\n")[0].strip()[:200] if res else ""
                if tname == "extract_software_components" and first_line:
                    structural_parts.append("Software components: " + first_line)
                elif tname == "extract_ports_tool" and first_line:
                    structural_parts.append("Ports: " + first_line)
            structural_summary = "\n".join(structural_parts) if structural_parts else "See Tool Results above for structural details (SWCs, ports, packages, data types)."
            comm_line = "See Tool Results for communication validation output."
            for line in factual_lines:
                if line.startswith("Communication:"):
                    comm_line = line.replace("Communication: ", "").strip()
                    break
            if det["validation_errors"]:
                final_verdict = "The file is incomplete or not compliant. Issues: " + "; ".join(det["validation_errors"]) + ". Address the recommendations below."
            else:
                final_verdict = "The file passed all validation checks covered by the tools. No critical issues found."
            report_sections = [
                "## Structural Summary",
                "",
                structural_summary,
                "",
                "## Validation Errors",
                "",
                "\n".join("- " + e for e in det["validation_errors"]) if det["validation_errors"] else "None.",
                "",
                "## Communication Analysis",
                "",
                comm_line,
                "",
                "## UUID Consistency",
                "",
                det["uuid_consistency"],
                "",
                "## Risk Assessment",
                "",
                "\n".join("- " + r for r in det["risk_assessment"]),
                "",
                "## Final Verdict",
                "",
                final_verdict,
                "",
                "## Recommendations",
                "",
                "\n".join("- " + rec for rec in det["recommendations"]) if det["recommendations"] else "None.",
            ]
            full_report = "\n".join(report_sections)
            return {
                "messages": [AIMessage(content=full_report)],
                "iteration_count": state["iteration_count"] + 1
            }

        if critical_issues_requested:
            summary_content += (
                "\nCRITICAL-ISSUES RULES (follow strictly):\n"
                "- The 'Critical Issues' section must list ONLY real failures. If a tool output contains "
                "✅ or 'passed' or 'No duplicate UUIDs found' or 'All valid' or 'no issues', that is NOT "
                "a critical issue—do not put it under Critical Issues.\n"
                "- WRONG: Putting 'Duplicate UUIDs not found' or 'check_duplicate_uuids_tool did not "
                "report any duplicate UUIDs' under Critical Issues. Right: only list items where a tool "
                "reported an actual failure (❌, 'failed', 'missing', 'broken', 'unsupported', 'issues found').\n"
                "- When validate_port_references_tool or validate_data_consistency_tool report errors "
                "(e.g. 'Interface reference not found', broken port refs), list them under Critical Issues "
                "as 'Missing/broken interface definitions' with the paths or port names from the tool output.\n"
                "- When validate_component_refs_tool reports errors (undefined COMPONENT-PROTOTYPE TYPE-TREF), "
                "list them under Critical Issues as 'Undefined software component' (e.g. CompB type missing).\n"
                "- Do NOT recommend 'verify manually' or 're-check' for tools that reported success.\n"
                "- In Recommendations and final answer, only mention and recommend fixes for the actual "
                "failures (e.g. unsupported version, missing BSW modules). Do not mention duplicate UUIDs "
                "or UUID verification when the duplicate-UUID tool reported no duplicates.\n"
                "- You may have a 'Passed Checks' section for tools that reported no issues; those must "
                "not appear under Critical Issues."
            )
        if validation_report_requested:
            summary_content += (
                "\nVALIDATION REPORT RULES (follow strictly):\n"
            )
            if mandatory_failures_block:
                summary_content += "- Include every item from the MANDATORY Failures block above in your Failures/Issues section.\n"
            # Ensure the narrative strictly follows the FACTUAL RESULTS block.
            summary_content += (
                "- Use the FACTUAL RESULTS block above as ground truth and do NOT contradict it. For example, if it says "
                "\"UUID: No duplicate UUIDs found.\", you must state that no duplicate UUIDs were found and you must not "
                "recommend removing duplicate UUIDs.\n"
                "- If FACTUAL RESULTS contains 'Ports/Interfaces: Missing/broken interface definitions present' or "
                "'Components: Undefined software component references present', you must list these under Validation "
                "Errors and treat them as high risk items.\n"
                "- Before giving your final answer, mentally check: Have you included every non-OK FACTUAL RESULTS line "
                "under Validation Errors or Risk Assessment, and avoided contradicting any of them?\n"
                "- CRITICAL: Read each tool's output. If a tool output contains errors (e.g. 'Interface reference "
                "not found', 'not found', 'CompB type missing', 'failed'), do NOT state that that validation "
                "'passed'. Only list a check under Successes/Passed when the tool output clearly indicates "
                "success (e.g. 'passed', 'All valid', 'no issues', no error lines).\n"
                "- If validate_port_references_tool or validate_data_consistency_tool output includes "
                "'Interface reference not found', 'not found', or similar error text, list those under "
                "Failures/Issues and do NOT write 'Port reference validation passed' or 'port interface "
                "references were found to be valid' or 'Component reference validation passed'.\n"
                "- When validate_component_refs_tool output reports undefined component references "
                "(e.g. 'CompB type missing'), list under Failures/Issues as 'Undefined software component' "
                "and do NOT state that 'Component reference validation passed' or 'All component references "
                "are defined'.\n"
                "- Include an 'Issues found' or 'Failures' section that lists ALL tool-reported failures "
                "(missing/broken interface definitions, undefined CompB, version, BSW, duplicate ports if any).\n"
                "- List under Failures ONLY what tools explicitly reported as failed (❌, 'failed', 'missing', "
                "'broken', 'unsupported', 'issues found').\n"
                "- If a tool output says 'passed' or 'No duplicate UUIDs found' or 'All valid', that check "
                "PASSED—put it under Successes/Passed, NOT under Failures. Do not say the tool 'did not pass' "
                "when it reported no duplicates or passed.\n"
                "- Do NOT recommend 'review duplicate UUIDs' or 'fix duplicate UUIDs' when check_duplicate_uuids_tool "
                "reported 'No duplicate UUIDs found'. Only recommend fixes for actual failures (e.g. version, BSW modules).\n"
                "- When duplicate_ports_tool reports 'No duplicate ports found', that is a pass; do not list it under Failures."
            )
        summary_content += "\nProvide a clear, comprehensive answer to the user's query based on these results."
        
        # Use LLM to generate summary (NO tools bound)
        prompt = ChatPromptTemplate.from_messages([
            ("system", summary_content),
            ("human", "Summarize the results and provide a clear answer to the user's query.")
        ])
        
        chain = prompt | llm
        response = chain.invoke({})
        
        return {
            "messages": [AIMessage(content=response.content if hasattr(response, 'content') else str(response))],
            "iteration_count": state["iteration_count"] + 1
        }
    
    return summary_node


def create_rag_fallback_node(upload_folder: str = "uploads"):
    """Create a RAG fallback node for when tools are insufficient."""
    def rag_fallback_node(state: AgentState) -> AgentState:
        """Use RAG to answer the query when tools fail or for complex questions."""
        try:
            from ai.rag_validation import process_rag_only
            
            messages = state["messages"]
            user_query = ""
            for m in reversed(messages):
                if isinstance(m, HumanMessage):
                    user_query = m.content if hasattr(m, "content") else str(m)
                    break
            selected_file = state.get("selected_file")
            # Resolve selected_file to filename for RAG (state may hold path)
            if selected_file and os.path.sep in selected_file:
                selected_file = os.path.basename(selected_file)
            
            # Use RAG only (no agent re-entry)
            rag_result = process_rag_only(
                user_query, 
                upload_folder, 
                selected_file=selected_file
            )
            
            return {
                "rag_result": rag_result,
                "messages": [AIMessage(content=rag_result)]
            }
        except Exception as e:
            error_msg = f"❌ RAG fallback error: {str(e)}"
            return {
                "rag_result": error_msg,
                "messages": [AIMessage(content=error_msg)]
            }
    
    return rag_fallback_node


def should_continue_after_planning(state: AgentState) -> Literal["tools", "rag", "end"]:
    """Determines routing after planning node."""
    # Check if we should use RAG
    if state.get("use_rag"):
        intent = state.get("intent", "unknown")
        if intent in ["question", "unknown"]:
            return "rag"
    
    # If we have a plan, go to tools
    plan = state.get("plan", [])
    if plan:
        return "tools"
    
    # Otherwise, end
    return "end"


def create_agent_graph(
    selected_file: Optional[str] = None,
    upload_folder: str = "uploads",
    checkpointer=None,
):
    """
    Creates an enhanced LangGraph agent with planning, memory, and RAG fallback.
    
    Args:
        selected_file: Currently selected ARXML file (if any)
        upload_folder: Path to uploads folder
        checkpointer: Optional shared checkpointer for conversation memory across requests.
            If None, uses get_shared_checkpointer() so thread_id-based history is preserved.
        
    Returns:
        Compiled LangGraph agent with memory
    """
    llm = get_llm()
    tools = get_all_tools()
    
    # Create specialized nodes (NO automatic tool calling)
    planning_node = create_planning_node(llm, tools, selected_file)
    tool_execution_node = create_tool_execution_node(selected_file, upload_folder)
    decide_next_node = create_decide_next_node(llm)
    summary_node = create_summary_node(llm, selected_file)
    rag_fallback_node = create_rag_fallback_node(upload_folder)
    
    # Build the graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("planning", planning_node)
    workflow.add_node("tools", tool_execution_node)
    workflow.add_node("decide_next", decide_next_node)
    workflow.add_node("summary", summary_node)
    workflow.add_node("rag", rag_fallback_node)
    
    # Set entry point
    workflow.set_entry_point("planning")
    
    # Add conditional edges from planning
    workflow.add_conditional_edges(
        "planning",
        should_continue_after_planning,
        {
            "tools": "tools",
            "rag": "rag",
            "end": END
        }
    )
    
    # After tools execute, decide whether to run more tools or summarize
    workflow.add_edge("tools", "decide_next")
    workflow.add_conditional_edges(
        "decide_next",
        should_continue_after_tools,
        {"summary": "summary", "tools": "tools"}
    )
    
    # After summary, end
    workflow.add_edge("summary", END)
    
    # After RAG, end
    workflow.add_edge("rag", END)
    
    # Use shared checkpointer so conversation memory persists across requests
    memory = checkpointer if checkpointer is not None else get_shared_checkpointer()
    return workflow.compile(checkpointer=memory)


def run_agent_query(
    user_query: str,
    selected_file: Optional[str] = None,
    upload_folder: str = "uploads",
    thread_id: str = "default"
) -> str:
    """
    Runs an agent query with planning, tool execution, memory, and RAG fallback.
    
    Args:
        user_query: User's question about ARXML files
        selected_file: Selected ARXML file (if any)
        upload_folder: Path to uploads folder
        thread_id: Thread ID for conversation memory
        
    Returns:
        Agent's response to the query
    """
    try:
        # Build file path if selected_file is provided
        file_path = None
        if selected_file:
            file_path = os.path.join(upload_folder, selected_file)
            if not os.path.exists(file_path):
                if os.path.exists(selected_file):
                    file_path = selected_file
                else:
                    file_path = selected_file  # Let tools handle the error
        
        # Create agent graph with shared checkpointer so thread_id preserves history
        agent = create_agent_graph(
            selected_file=selected_file,
            upload_folder=upload_folder,
            checkpointer=get_shared_checkpointer(),
        )
        
        # Initialize state: only the new message; checkpointer merges in prior history for this thread_id
        config = {"configurable": {"thread_id": thread_id}}
        initial_state = {
            "messages": [HumanMessage(content=user_query)],
            "selected_file": file_path,
            "tool_results": [],
            "plan": None,
            "intent": None,
            "iteration_count": 0,
            "use_rag": False,
            "rag_result": None
        }
        
        # Run agent and collect final state
        final_state = None
        try:
            for event in agent.stream(initial_state, config):
                for node_name, node_state in event.items():
                    final_state = node_state
        except RuntimeError as re:
            if "cannot schedule new futures after shutdown" in str(re):
                logger = logging.getLogger(__name__)
                logger.warning("Agent stream interrupted (executor shutdown): %s", re)
                return "Request was interrupted (app may be stopping). Please try again."
            raise

        # Extract final response
        if final_state:
            messages = final_state.get("messages", [])
            
            # Check for RAG result first
            if final_state.get("rag_result"):
                return final_state["rag_result"]
            
            # Find the last AI message that's not a tool call
            for msg in reversed(messages):
                if isinstance(msg, AIMessage):
                    # If it has tool calls, we need to wait for tool execution
                    if not (hasattr(msg, 'tool_calls') and msg.tool_calls):
                        return msg.content if hasattr(msg, 'content') else str(msg)
            
            # If we only have tool calls, get the last message content
            if messages:
                last_msg = messages[-1]
                if isinstance(last_msg, AIMessage):
                    return last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
        
        return "❌ Agent execution completed but no response generated."

    except Exception as e:
        import traceback
        logger = logging.getLogger(__name__)
        logger.exception("Agent execution failed")
        return f"❌ Error during agent execution: {str(e)}. Please try again or rephrase your query."


def run_agent_query_structured(
    user_query: str,
    selected_file: Optional[str] = None,
    upload_folder: str = "uploads",
    thread_id: str = "default",
) -> dict:
    """
    Runs the agent and returns a structured result for dashboard UI.
    Returns: {"command", "plan", "tool_results", "summary", "steps"}
    """
    command = user_query
    empty = {
        "command": command,
        "plan": [],
        "tool_results": [],
        "summary": "",
        "steps": [],
    }
    try:
        file_path = None
        if selected_file:
            file_path = os.path.join(upload_folder, selected_file)
            if not os.path.exists(file_path) and os.path.exists(selected_file):
                file_path = selected_file
            elif not os.path.exists(file_path):
                file_path = selected_file
        agent = create_agent_graph(
            selected_file=selected_file,
            upload_folder=upload_folder,
            checkpointer=get_shared_checkpointer(),
        )
        config = {"configurable": {"thread_id": thread_id}}
        initial_state = {
            "messages": [HumanMessage(content=user_query)],
            "selected_file": file_path,
            "tool_results": [],
            "plan": None,
            "intent": None,
            "iteration_count": 0,
            "use_rag": False,
            "rag_result": None,
        }
        final_state = None
        try:
            for event in agent.stream(initial_state, config):
                for node_name, node_state in event.items():
                    final_state = node_state
        except RuntimeError as re:
            if "cannot schedule new futures after shutdown" in str(re):
                logger = logging.getLogger(__name__)
                logger.warning("Agent stream interrupted (executor shutdown): %s", re)
                return {**empty, "summary": "Request was interrupted (app may be stopping). Please try again."}
            raise
        if not final_state:
            return {**empty, "summary": "❌ Agent execution completed but no response generated."}
        plan = final_state.get("plan") or []
        tool_results = final_state.get("tool_results") or []
        summary = ""
        if final_state.get("rag_result"):
            summary = final_state["rag_result"]
            steps = ["Planning", "RAG"]
        else:
            messages = final_state.get("messages", [])
            for msg in reversed(messages):
                if isinstance(msg, AIMessage) and not (hasattr(msg, "tool_calls") and msg.tool_calls):
                    summary = msg.content if hasattr(msg, "content") else str(msg)
                    break
            if not summary and messages:
                last_msg = messages[-1]
                if isinstance(last_msg, AIMessage):
                    summary = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
            if not summary:
                summary = "❌ Agent execution completed but no response generated."
            steps = ["Planning"] + [f"Tool: {s.get('tool_name', '')}" for s in plan] + ["Summary"]
        return {
            "command": command,
            "plan": plan,
            "tool_results": tool_results,
            "summary": summary,
            "steps": steps,
        }
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception("Agent execution failed")
        return {**empty, "summary": f"❌ Error during agent execution: {str(e)}. Please try again or rephrase your query."}
