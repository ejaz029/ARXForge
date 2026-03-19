"""
LLM-based engineering report for ARXML comparison.
Uses deterministic comparison output from validators.compare_arxml; LLM only explains.
"""
from langchain_core.messages import SystemMessage, HumanMessage
from validators.compare_arxml import format_comparison_for_report
from config.llm_config import get_llm


def summarize_comparison_with_llm(result_dict: dict, name_a: str, name_b: str) -> str:
    """
    Build a structured text from the comparison result and ask the LLM for an
    engineering report. Returns the report string or an error message starting
    with "Engineering report unavailable" or "Could not".
    """
    if result_dict.get("error"):
        return f"Engineering report unavailable: {result_dict['error']}"
    try:
        formatted = format_comparison_for_report(result_dict, name_a, name_b)
    except Exception as e:
        return f"Could not format comparison: {e}"

    system_prompt = (
        "You are an AUTOSAR engineer. Given the structural comparison data below, "
        "produce a concise ENGINEERING REPORT with two parts: "
        "(1) COMPARISON SUMMARY — architecture, interfaces, data model changes in brief; "
        "(2) ENGINEERING ANALYSIS — Impact summary, Risk analysis (use the severity rules given), "
        "and Testing recommendations. Use only the facts and numbers provided; do not contradict them. "
        "Do not dump raw paths; keep the report short and scannable."
    )
    user_content = f"Generate the engineering report for this comparison:\n\n{formatted}"

    try:
        llm = get_llm()
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content),
        ])
        text = response.content if hasattr(response, "content") else str(response)
        if not (text and text.strip()):
            return "Engineering report unavailable: empty LLM response."
        return text.strip()
    except Exception as e:
        return f"Engineering report unavailable: {e}"
