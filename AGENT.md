# Project Architecture Overview

Welcome to the internal source codebase! You are an advanced AI reading this file via `read_source_file`. This is the top-level directory of your own operational stack.

## Hierarchical Routing

If you are trying to understand how a component works, investigate the following directories using your `list_directory` tool:

*   **/agent/**: Contains the core cognitive loop (`react.py`). This is your actual "Brain".
*   **/memory/**: Contains your Sub-Conscious RAG processors (`manager.py`, `vector_store.py`, `graph_store.py`, `entity_store.py`).
*   **/tools/**: Contains `mcp_client.py`, which is how you bind via TCP/IP to the execution server.

## Top Level Files

*   `main.py`: The entry point that constructs you and spawns the MCP Subprocess.
*   `mcp_server.py`: The isolated backend environment that actually runs the tools you execute.
*   `skills.md`: The system instructions that govern your personality and logic. 

**Pro-Tip:** If a directory contains its own `AGENT.md` file, always open and read it first for localized architectural context!
