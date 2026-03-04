# ARXML Agentic AI Test Suite

Comprehensive testing suite for the ARXML Agentic AI system, organized into 7 phases.

## Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── test_tools.py            # Phase 1: Tool unit tests
├── test_intent_router.py    # Phase 2: Intent routing tests
├── test_planning.py         # Phase 3: Planning node tests
├── test_tool_chaining.py    # Phase 4: Multi-step tool execution
├── test_rag_fallback.py     # Phase 5: RAG fallback tests
├── test_memory.py           # Phase 6: Conversation memory tests
└── test_stress.py           # Phase 7: Stress tests
```

## Running Tests

### Run all tests
```bash
pytest tests/ -v
```

### Run specific phase
```bash
# Phase 1: Tools
pytest tests/test_tools.py -v

# Phase 2: Intent Router
pytest tests/test_intent_router.py -v

# Phase 3: Planning
pytest tests/test_planning.py -v

# Phase 4: Tool Chaining
pytest tests/test_tool_chaining.py -v

# Phase 5: RAG Fallback
pytest tests/test_rag_fallback.py -v

# Phase 6: Memory
pytest tests/test_memory.py -v

# Phase 7: Stress
pytest tests/test_stress.py -v
```

### Run with output
```bash
pytest tests/ -v -s  # -s shows print statements
```

### Run specific test
```bash
pytest tests/test_tools.py::TestToolExtraction::test_extract_software_components -v
```

## Test Phases

### Phase 1: Unit Testing (Tools Level)
- Tests each of the 13 tools independently
- No agent logic involved
- Verifies tools work correctly in isolation

### Phase 2: Intent Router Testing
- Tests intent classification accuracy
- Edge cases (random questions, mixed intents)
- Tool recommendations
- RAG decision logic

### Phase 3: Agent Planning Test
- Tests planning node in isolation
- Verifies multi-step plan generation
- Plan structure validation

### Phase 4: Tool Chaining Test
- Multi-step query execution
- Tool execution tracking
- Result merging verification

### Phase 5: RAG Fallback Test
- RAG triggering for questions
- RAG vs tools decision
- Context usage in RAG

### Phase 6: Memory Test
- Conversation context retention
- Multi-turn conversations
- Memory isolation between threads

### Phase 7: Stress Test
- Complex multi-step queries
- Sequential execution
- Error recovery
- Resource usage

## What to Watch For

During testing, monitor for:

- ✅ **Hallucinated tool outputs**: Tools should return real data
- ✅ **Infinite loops**: Agent should complete within timeout
- ✅ **Wrong intent classification**: Intents should match query type
- ✅ **Tool selection mismatch**: Right tools for right queries
- ✅ **Memory leakage**: Memory should be isolated per thread
- ✅ **RAG triggered incorrectly**: RAG only for questions/unknown
- ✅ **Partial execution failure**: Should handle errors gracefully

## Requirements

- pytest
- Test ARXML files in `uploads/` folder
- Valid API keys in `.env` or `config.yaml`

## Notes

- Some tests require actual ARXML files in the `uploads/` folder
- Tests that use LLM may take time and consume API credits
- Stress tests have timeouts to prevent hanging
- Memory tests use thread IDs to isolate conversations
