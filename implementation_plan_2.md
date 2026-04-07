# Agent Upgrade Implementation Plan

This document outlines the changes to fulfill the user's new requests while sticking to the lightweight custom loop.

## Overview of Changes

1. **Model API Update (Ollama)**: Update defaults throughout the codebase (`main.py`, `react.py`, `manager.py`) to point to `ollama/qwen3:4b` utilizing LiteLLM.
2. **System Prompt Externalization**: Introduce a `skills.md` file containing the core instructions. The `ReActAgent` will read this file during initialization, instead of using a hardcoded string.
3. **Markdown Diary**: Introduce a `memory/diary/` system. Every time the agent processes information or answers, it will log the interaction into a `YYYY-MM-DD.md` markdown file in a readable format. We will expose an `internal` tool called `list_diaries` and `read_diary` to the ReAct agent, allowing it to browse its own past markdown files explicitly if it wishes to reflect deeply.
4. **Vector-Searchable Graph Nodes**: Update `GraphStore` to utilize `fastembed`. When adding a node to the graph, we will compute its vector embedding. Instead of failing when an exact string match for a node isn't found, we will search for the nearest neighbor via cosine similarity (e.g. searching for "Apple" will find the node "Apples" or related concepts as starting points for graph traversal).
5. **Graph Deletion & Modification**: Add explicit methods to `GraphStore` to delete specific triplets or nodes. We will expose these graph operations as well as memory operations to the agent via `internal` tools (e.g. `add_knowledge`, `delete_knowledge`).

## Open Questions

> [!WARNING]
> Please review and provide feedback on these questions before we proceed:
> 1. **Model name verification**: You requested `qwen3:4b`. Assuming Ollama is installed and running, LiteLLM accepts `ollama/qwen3:4b`. Are you certain about the model tag? (Often Ollama tags are like `qwen2.5:3b`, etc., I will use exactly what you requested but please ensure the model is pulled locally).
> 2. **Diary Granularity**: The diary will by default append any user query and agent final answer as beautifully formatted markdown blocks. Is this sufficient, or do you want the entire thought process logged in the diary as well?

## Proposed Changes

### Configuration Strategy
#### [NEW] `skills.md`
Will contain the baseline ReAct loop instructions + any additional skills you decide to configure.

### LLM Defaults Update
#### [MODIFY] `main.py`
Change model initializations to `ollama/qwen3:4b` and remove explicit GEMINI_API warnings.

#### [MODIFY] `memory/manager.py`
Update defaults and utilize the internal tool registration.

### Diary Engine
#### [NEW] `memory/diary.py`
A simple class that appends observations into `diary/YYYY-MM-DD.md`.

### Tool Execution Overhaul
#### [MODIFY] `agent/react.py`
Update the tool execution block to intercept calls meant for the `"internal"` server. Provide tools like:
- `internal.read_diary(date)`: Reads the markdown file.
- `internal.delete_memory(entity)`: Deletes associated node and edges from the graph.

### Graph Vectorization
#### [MODIFY] `memory/graph_store.py`
Inject `TextEmbedding`. Maintain an in-memory dictionary of node strings to their embedding. On querying, use numpy to compute distances quickly.

## Verification Plan

We will run the agent with `$env:LITELLM_LOG="DEBUG"` (if needed) and perform a few test queries to verify Ollama executes locally without crashing. We will test deleting a fact and ensuring it disappears from the graph file.
