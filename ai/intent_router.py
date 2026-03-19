"""
Intent routing system for classifying user queries and determining the best validation approach.
"""
from typing import Literal, Dict, List
from langchain_core.prompts import ChatPromptTemplate
from config.llm_config import get_llm

# Intent categories
IntentType = Literal[
    "extraction",      # Extract components, ports, ECUs
    "validation",     # Run validation checks
    "analysis",       # Complex multi-step analysis
    "question",       # General questions about ARXML
    "comparison",     # Compare files or components
    "unknown"         # Fallback
]

# Intent keywords mapping
INTENT_KEYWORDS: Dict[IntentType, List[str]] = {
    "extraction": [
        "extract", "list", "show", "find", "get", "display",
        "components", "ports", "ecus", "instances", "software"
    ],
    "validation": [
        "validate", "check", "verify", "test", "audit",
        "schema", "consistency", "duplicate", "error", "issue",
        "memory", "communication", "rte", "diagnostics", "bsw",
        "reference", "referenced", "defined", "properly",
        "required", "interfaces", "missing", "interface"
    ],
    "analysis": [
        "analyze", "examine", "investigate", "review", "assess",
        "comprehensive", "full", "complete", "all", "everything"
    ],
    "question": [
        "what", "how", "why", "when", "where", "explain", "describe",
        "tell me", "help", "information", "about"
    ],
    "comparison": [
        "compare", "difference", "similar", "versus", "vs", "between"
    ]
}


def classify_intent(user_query: str) -> IntentType:
    """
    Classify user query intent using keyword matching and LLM.
    Prioritizes question words over content words.
    
    Args:
        user_query: User's input query
        
    Returns:
        Detected intent type
    """
    query_lower = user_query.lower().strip()
    
    # Priority 1: Check for comparison keywords first (before question check)
    comparison_keywords = ["compare", "difference", "similar", "versus", "vs", "between"]
    if any(keyword in query_lower for keyword in comparison_keywords):
        # If it has comparison keywords, it's likely comparison
        # But check if it's a question about comparison
        question_words = ["what", "how", "why"]
        if query_lower.startswith(tuple(question_words)) and "difference" in query_lower:
            # "What's the difference" is still comparison, not question
            return "comparison"
        elif any(keyword in query_lower for keyword in comparison_keywords):
            return "comparison"
    
    # Treat "communication mappings" / "inconsistencies" + extract/check/report as analysis
    mapping_inconsistency = any(w in query_lower for w in ("communication", "mappings", "inconsistencies"))
    action_or_target = any(w in query_lower for w in ("extract", "check", "report", "components"))
    if mapping_inconsistency and action_or_target:
        return "analysis"
    
    # Treat "which are duplicated" / "duplicate ports" etc. as validation (run duplicate tools)
    duplicate_asking = any(w in query_lower for w in ("duplicate", "duplicated", "repeated"))
    if duplicate_asking:
        return "validation"

    # Treat "critical issues" / "most critical issues" / "issues in this file" as analysis (run validators, then summarize)
    critical_issues_phrases = [
        "critical issue", "critical issues", "most critical", "key issues",
        "issues in this file", "problems in this file", "what's wrong", "what is wrong",
        "any issues", "any problems", "find issues", "identify issues"
    ]
    if any(phrase in query_lower for phrase in critical_issues_phrases):
        return "analysis"

    # Treat "structured engineering report" / "structured report" / "engineering report" as analysis (same validator set)
    structured_report_phrases = [
        "structured engineering report", "structured report", "engineering report",
        "generate a report", "comprehensive report"
    ]
    if any(phrase in query_lower for phrase in structured_report_phrases):
        return "analysis"

    # Treat "complete audit" / "full audit" / "enterprise audit" as analysis (same validator set)
    audit_phrases = [
        "complete audit", "full audit", "run an audit", "run a complete audit",
        "enterprise audit", "enterprise-level audit", "enterprise level"
    ]
    if any(phrase in query_lower for phrase in audit_phrases):
        return "analysis"

    # NL architecture queries: which SWCs use X, what depends on Y -> analysis (use query tools)
    if any(phrase in query_lower for phrase in (
        "which swc", "which swcs", "which component", "which components",
        "who uses", "what depends on", "what uses", "which use interface"
    )):
        return "analysis"

    # Priority 2: Check for question words (but not if it's comparison)
    question_words = ["what", "how", "why", "when", "where", "explain", "describe", "tell me"]
    question_patterns = [
        query_lower.startswith(tuple(question_words)),
        any(f"{word} is" in query_lower or f"{word} are" in query_lower for word in question_words),
        any(f"{word} does" in query_lower or f"{word} do" in query_lower for word in question_words),
        query_lower.endswith("?")
    ]
    
        # If it's clearly a question (starts with question word or ends with ?)
    if any(question_patterns):
        count_phrases = ["how many", "number of", "count of", "how many of"]
        presence_phrases = ["are there any", "is there any", "does this file have", "are there ", "are all"]
        extraction_targets = ["port", "component", "ecu", "instance", "software", "uuid"]
        validation_question_phrases = ["properly defined", "correctly defined", "valid reference", "references valid"]
        # "Are all referenced ports properly defined?" -> validation (check before extraction)
        if "port" in query_lower and any(phrase in query_lower for phrase in validation_question_phrases):
            return "validation"
        # Count-style questions -> extraction
        if any(phrase in query_lower for phrase in count_phrases) and any(
            target in query_lower for target in extraction_targets
        ):
            return "extraction"
        # Presence-style questions -> extraction
        if any(phrase in query_lower for phrase in presence_phrases) and any(
            target in query_lower for target in extraction_targets
        ):
            return "extraction"
        # Check if it's asking about something (not an action)
        action_words = ["extract", "validate", "check", "run", "show", "list", "get", "display"]
        if not any(word in query_lower for word in action_words):
            return "question"
    
    # Priority 3: Check for action keywords with weighted scoring
    intent_scores: Dict[IntentType, int] = {
        "extraction": 0,
        "validation": 0,
        "analysis": 0,
        "question": 0,
        "comparison": 0,
        "unknown": 0
    }
    
    # Check for analysis indicators (comprehensive, multi-step)
    analysis_indicators = ["comprehensive", "analyze", "analysis", "everything", "all", "complete", "full"]
    if any(indicator in query_lower for indicator in analysis_indicators):
        # If query has multiple action words + analysis indicators, it's analysis
        action_count = sum([
            "extract" in query_lower,
            "validate" in query_lower,
            "check" in query_lower,
            "analyze" in query_lower
        ])
        if action_count >= 2:
            intent_scores["analysis"] += 5  # High weight for multi-step analysis
    
    for intent, keywords in INTENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in query_lower:
                # Give higher weight to question keywords
                if intent == "question":
                    intent_scores[intent] += 2
                elif intent == "analysis":
                    intent_scores[intent] += 2  # Analysis also gets higher weight
                else:
                    intent_scores[intent] += 1
    
    # Get highest scoring intent
    max_score = max(intent_scores.values())
    if max_score > 0:
        for intent, score in intent_scores.items():
            if score == max_score:
                return intent
    
    # Fallback to LLM-based classification for ambiguous queries
    try:
        llm = get_llm()
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Classify the user's query into one of these intents:
- extraction: User wants to extract/list/show components, ports, ECUs
- validation: User wants to validate/check/verify ARXML files
- analysis: User wants comprehensive multi-step analysis
- question: User asks general questions about ARXML
- comparison: User wants to compare files or components
- unknown: Cannot determine intent

Respond with ONLY the intent name."""),
            ("human", "{query}")
        ])
        
        chain = prompt | llm
        response = chain.invoke({"query": user_query})
        intent_str = response.content.strip().lower()
        
        # Validate response
        if intent_str in ["extraction", "validation", "analysis", "question", "comparison", "unknown"]:
            return intent_str
    except Exception:
        pass
    
    return "unknown"


def get_recommended_tools(intent: IntentType) -> List[str]:
    """
    Get recommended tools based on intent.
    
    Args:
        intent: Classified intent type
        
    Returns:
        List of recommended tool names
    """
    tool_mapping: Dict[IntentType, List[str]] = {
        "extraction": [
            "extract_software_components",
            "extract_ports_tool",
            "extract_ecu_instances",
            "extract_uuids_tool"
        ],
        "validation": [
            "validate_schema_tool",
            "validate_data_consistency_tool",
            "validate_port_references_tool",
            "validate_component_refs_tool",
            "duplicate_ports_tool",
            "check_duplicate_uuids_tool",
            "validate_swc_tool",
            "validate_communication_tool",
            "validate_memory_tool",
            "validate_rte_tool",
            "validate_diagnostics_tool",
            "validate_ecu_bsw_tool",
            "validate_version_compatibility_tool"
        ],
        "analysis": [
            "extract_software_components",
            "extract_ports_tool",
            "validate_data_consistency_tool",
            "validate_port_references_tool",
            "validate_component_refs_tool",
            "duplicate_ports_tool",
            "check_duplicate_uuids_tool",
            "validate_version_compatibility_tool",
            "validate_swc_tool",
            "validate_communication_tool",
            "validate_memory_tool",
            "validate_rte_tool",
            "validate_diagnostics_tool",
            "validate_ecu_bsw_tool",
            "list_swcs_using_interface_tool",
            "list_dependents_of_signal_or_message_tool"
        ],
        "question": [],  # Use RAG for questions
        "comparison": [
            "extract_software_components",
            "extract_ports_tool",
            "extract_ecu_instances"
        ],
        "unknown": []  # Use RAG fallback
    }
    
    return tool_mapping.get(intent, [])


def should_use_rag(intent: IntentType, query_complexity: str = "medium") -> bool:
    """
    Determine if RAG should be used instead of or alongside tools.
    
    Args:
        intent: Classified intent
        query_complexity: "simple", "medium", "complex"
        
    Returns:
        True if RAG should be used
    """
    # Use RAG for questions, unknown intents, or complex queries
    if intent in ["question", "unknown"]:
        return True
    
    if query_complexity == "complex" and intent == "analysis":
        return True
    
    return False
