# Implementation Plan: Standalone Internal MCP Server

The goal is to cleanly decouple the agent's core reasoning logic (`react.py`) from the explicit Python tool execution logic by wrapping our custom operations into a formal Model Context Protocol (MCP) server.

## Architectural Challenge: State Synchronization
Currently, `MemoryManager`, `EntityStore`, and `GraphStore` cache JSON data in memory to dramatically speed up vector embeddings. If we split the tool execution (like `upsert_entity`) into a separate `mcp_server.py` process running via Stdio, it will update the disk files, but the original `MemoryManager` sitting in `main.py` (which creates the query contexts) won't know the files changed, leading to stale memory states.

## Proposed Architecture: The "Memory-as-a-Service" Shift

To solve this and strictly separate concerns:
1. **`mcp_server.py` (The Source of Truth)**: 
    * We will create a `fastmcp` server here.
    * It will exclusively own and instantiate `MemoryManager` and `Diary`.
    * We will migrate **all** currently internal tools (`read_diary`, `upsert_entity`, `delete_graph_node`, `validate_source`) into standard `@mcp.tool()` definitions within this server.
    * We will add two *new* tools specifically for the Agent context loop: `get_memory_context(query)` and `add_user_memory(text)`.

2. **`agent/react.py` (The Pure Reasoner)**:
    * We will remove all the `elif tool == ...` hardcoding.
    * We will remove the `self.memory` dependency entirely. 
    * During the setup of `process_user_query`, instead of `self.memory.query_memory(query)`, the agent will rely on standard MCP communication.

3. **`main.py` (The Orchestrator)**:
    * It will no longer instantiate `MemoryManager` directly.
    * It will instruct `MCPClientManager` to launch: `python mcp_server.py` as an Stdio process.
    * It will pass the user's query into the `ReActAgent`.

## Open Questions

> [!WARNING]
> Please review and provide feedback:
> 1. Moving the `Memory Manager` entirely behind the MCP Server makes the architecture extremely clean, but it means `main.py` must use MCP tools to fetch the initial prompt context before the main loop starts. Do you approve of making the MCP server the *exclusive* owner of the memory databases? 
> 2. Have you installed `fastmcp` or relies on the base `mcp` library? I plan to use the standard Python `mcp` library (Server class) which is natively in the dependencies.

## Execution Steps
1. **[NEW]** `mcp_server.py`: Initialize a formal MCP server. Expose all memory and tool functionalities via the `@server.tool()` decorator.
2. **[MODIFY]** `agent/react.py`: Strip out the massive `if str == internal:` code blocks. Allow the agent to just use the standard `self.mcp.call_tool` pattern.
3. **[MODIFY]** `main.py`: Setup the subprocess connection and remove local Memory dependencies.

## Verification
- Start `main.py`. It should immediately launch the secondary invisible `mcp_server.py` process.
- The agent should successfully query memory and manage entities completely transparently over the MCP protocol without having python classes hardlinked.
