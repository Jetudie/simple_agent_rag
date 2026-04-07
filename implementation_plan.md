# AI Agent Architecture Plan

This document outlines the architecture and implementation steps for building an AI agent with long-term memory (GraphRAG + Vector RAG), high-discretion reasoning (OpenEvidence style), precise research capabilities via the Model Context Protocol (MCP), and a ReAct core loop.

## Overview

We will build a modular Python application consisting of:
1.  **ReAct Core Loop**: A custom reasoning loop that strictly enforces the ReAct (Reasoning and Acting) pattern. To achieve "high discretion" mimicking OpenEvidence, the system prompt will rigidly instruct the agent to only rely on verifiable facts, cite memory or search results, and admit unknowns when evidence is lacking.
2.  **Dual-System Long-term Memory**:
    *   **Vector RAG**: Uses `qdrant-client` and `fastembed` to store text chunks semantically. Excellent for recalling broad contexts and documents.
    *   **GraphRAG**: Uses `networkx` to store Entity-Relationship-Entity triplets extracted from interactions. Excellent for precise, multi-hop reasoning over structured facts.
3.  **MCP Tooling Protocol**: We will implement an `MCPClient` leveraging standard MCP protocols to connect to external tool providers (e.g., standard MCP servers for web searching, filesystem access, etc.).

## Open Questions

> [!WARNING]
> Please review and provide feedback on these questions before we proceed:
> 1. **Language Model API**: Which LLM provider would you like to use for the core reasoning? (e.g., Gemini, OpenAI, Claude, local models like Ollama?) I plan to use `litellm` by default to support multiple providers via environment variables.
> 2. **MCP Servers**: Do you have specific MCP servers you want to connect to immediately for "precise research"? (e.g., a specific web search server or brave-search MCP)? I will build the client so you can easily plug them in via terminal commands.
> 3. **Persistence**: For Qdrant, we can use in-memory testing or file-based persistence. I will default to a local disk-based Qdrant database to ensure the "long term" aspect. Let me know if you prefer otherwise.

## Proposed Changes

### Dependencies and Core Setup

#### [NEW] `requirements.txt`
Will include: `qdrant-client`, `networkx`, `litellm`, `mcp`, `pydantic`, `fastembed` (for embeddings), `python-dotenv`, and `rich` (for elegant terminal UI).

***

### Memory Subsystem (Vector & Graph RAG)

#### [NEW] `memory/vector_store.py`
A wrapper around Qdrant local storage. It will chunk incoming documents/observations, embed them using local models via `fastembed`, and store them for semantic search retrieval.

#### [NEW] `memory/graph_store.py`
A class managing a `networkx` Directed Graph. It will store extracted knowledge triplets and have functions to extract subgraphs around specific query entities. 

#### [NEW] `memory/manager.py`
The overarching `MemoryManager`. When given new information, it uses the LLM to extract entity triplets (sent to Graph) and chunks the text (sent to Qdrant). When querying for context, it queries both stores and synthesizes the retrieved evidence.

***

### Core Agent and Tooling

#### [NEW] `tools/mcp_client.py`
Handles connections to local or remote MCP servers. Translates available MCP tools into descriptions the ReAct loop understands, and handles executing tool calls through the MCP protocol.

#### [NEW] `agent/react.py`
The ReAct execution engine. Contains the strict OpenEvidence-style system prompt. It manages chat history, iterates through Thought/Action/Observation cycles, retrieves from the `MemoryManager` dynamically, and formats final answers with citations.

#### [NEW] `main.py`
The orchestration file. Connects the components and provides an interactive CLI chat loop.

## Verification Plan

### Automated/Unit Tests
- Basic smoke tests to ensure Qdrant collection creation and NetworkX node additions work without crashing.
- Verify that the MCP client can successfully establish a transport connection to a basic server.

### Manual Verification
- Start the `main.py` agent loop.
- Tell it some facts (e.g., "Alice is working on project X"). The agent should save this.
- Restart the agent. Ask "What is Alice working on?". The agent should consult its GraphRAG/VectorRAG, find the context, and answer accurately.
- Ask questions requiring external tools (if a search MCP is connected) and ensure it reasons before acting, maintaining high discretion by citing exactly where it found the answer.
