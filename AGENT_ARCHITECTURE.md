# Agentic AI Architecture

## Overview
The ARXML Validator has been converted from a simple validator to a full **Agentic AI system** using LangGraph, with intent routing, planning, memory, and RAG fallback.

## Architecture Components

### 1. **Intent Router** (`ai/intent_router.py`)
- **Purpose**: Classifies user queries into intent categories
- **Intents**:
  - `extraction`: Extract components, ports, ECUs
  - `validation`: Run validation checks
  - `analysis`: Complex multi-step analysis
  - `question`: General questions about ARXML
  - `comparison`: Compare files or components
  - `unknown`: Fallback category
- **Features**:
  - Keyword-based classification
  - LLM-based classification for ambiguous queries
  - Tool recommendations based on intent
  - RAG usage decision logic

### 2. **Agent Tools** (`ai/agent_tools.py`)
- **Purpose**: Wraps all validators as LangChain tools
- **Available Tools**:
  - `extract_software_components`: Extract SWCs
  - `extract_ports_tool`: Extract P-PORTs and R-PORTs
  - `extract_ecu_instances`: Extract ECU instances
  - `check_duplicate_uuids_tool`: Check duplicate UUIDs
  - `validate_schema_tool`: Schema validation
  - `validate_data_consistency_tool`: Data consistency checks
  - `validate_swc_tool`: Software component validation
  - `validate_communication_tool`: Communication validation
  - `validate_memory_tool`: Memory validation
  - `validate_rte_tool`: RTE validation
  - `validate_diagnostics_tool`: Diagnostics validation
  - `validate_ecu_bsw_tool`: ECU/BSW validation
  - `validate_version_compatibility_tool`: Version compatibility

### 3. **LangGraph Agent** (`ai/arxml_agent.py`)
- **Purpose**: Main agent orchestrator with planning, memory, and tool execution
- **State Management**:
  ```python
  AgentState:
    - messages: Conversation history
    - selected_file: Current ARXML file
    - tool_results: Tool execution results
    - plan: Generated execution plan
    - intent: Classified intent
    - iteration_count: Execution counter
    - use_rag: Whether to use RAG
    - rag_result: RAG fallback result
  ```
- **Graph Nodes**:
  1. **Planning Node**: Generates step-by-step execution plan (validates tool names against TOOL_REGISTRY)
  2. **Tools Node**: Executes selected tools (can run multiple rounds)
  3. **Decide Next Node**: Optionally adds more tool steps based on results (iterative execution, up to MAX_ITERATIONS)
  4. **Summary Node**: Synthesizes tool results into a final answer
  5. **RAG Node**: Fallback for question/unknown intents (calls `process_rag_only`; no agent re-entry)
- **Features**:
  - **Planning**: LLM-generated execution plans
  - **Memory**: A single shared checkpointer (`get_shared_checkpointer()`) is reused across requests so that `thread_id` preserves conversation history; load history by using the same `thread_id` when calling the graph.
  - **Conditional Routing**: Planning → tools or RAG or end; after tools → decide_next → summary or another tools round
  - **RAG Fallback**: Automatic fallback to RAG when tools are insufficient; uses `process_rag_only` to avoid re-entering the agent
  - **Iterative tool execution**: After each tools run, the decide_next node can request more tools (max iterations cap in `MAX_ITERATIONS`)

### 4. **RAG Integration** (`ai/rag_validation.py`)
- **Purpose**: RAG-only path and single entry point for the app
- **Unified routing**:
  - **Single entry**: `process_query_with_rag()` decides agent vs RAG using `_is_complex_query()` (intent).
  - **Agent path**: For extraction, validation, analysis, comparison → `run_agent_query()`.
  - **RAG path**: For question/unknown → `process_rag_only()` (loads ARXML context, optional special handlers, then RAG QA).
  - The agent’s RAG node calls `process_rag_only()` so there is no re-entry into the agent.

### 5. **Chatbot Interface** (`ai/ai_chatbot.py`)
- **Purpose**: Streamlit UI for interacting with the agent
- **Features**:
  - Intent-based mode indicators
  - Conversation memory per file
  - Visual feedback for agent vs RAG mode

## Workflow

```
User Query
    ↓
process_query_with_rag (single entry)
    ↓
use_agent? ──No──→ process_rag_only → RAG QA → Response
    │
   Yes
    ↓
run_agent_query (shared checkpointer + thread_id)
    ↓
Planning Node (plan + validate tool names)
    ↓
tools / rag / end
    ↓
Tools Node → decide_next → (summary | tools again, up to MAX_ITERATIONS)
    ↓
Summary Node or RAG Node → Response
```

## Memory & Context

- **Shared checkpointer**: One `MemorySaver()` is created via `get_shared_checkpointer()` and passed into `create_agent_graph()`, so all requests in the same process share it and conversation history is preserved per `thread_id`.
- **Thread-based Memory**: Use the same `thread_id` (e.g. derived from selected file) across turns so the graph loads prior messages from the checkpointer.
- **Context retention**: Planning and summary nodes use the latest user message; the graph state holds full message history for the thread.

## Intent-Based Routing

| Intent | Tools Used | RAG Used |
|--------|-----------|----------|
| extraction | extract_* tools | No |
| validation | validate_* tools | No |
| analysis | Multiple tools | Sometimes |
| question | None | Yes |
| comparison | extract_* tools | Sometimes |
| unknown | None | Yes |

## Benefits

1. **Autonomous Decision Making**: Agent decides which validators to use
2. **Multi-step Planning**: Can break down complex queries into steps
3. **Context Awareness**: Remembers previous queries in conversation
4. **Intelligent Fallback**: Uses RAG when tools are insufficient
5. **Intent Understanding**: Routes queries to appropriate tools
6. **Scalable**: Easy to add new tools and validators

## Usage Example

```python
from ai.arxml_agent import run_agent_query

response = run_agent_query(
    user_query="Validate all software components and check for duplicate UUIDs",
    selected_file="SystemExtract.arxml",
    upload_folder="uploads",
    thread_id="system_extract"  # For conversation memory
)
```

## Configuration

- **Max Iterations**: `MAX_ITERATIONS` in `ai/arxml_agent.py` (default 5) caps the number of tool execution loops (plan → tools → decide_next → tools → …).
- **Memory**: Single shared LangGraph MemorySaver (in-memory); use the same checkpointer when compiling the graph so `thread_id` preserves history.
- **LLM**: Groq (configurable in `config/llm_config.py`)
- **DEBUG_AGENT**: Set in `config.yaml` or env to enable agent debug logging (e.g. tool registry print on import).
