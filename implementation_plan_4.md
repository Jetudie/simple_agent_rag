# Implementation Plan: Agent Self-Learning Notebooks

The goal is to provide the agent with a mutable workspace (`notes/`) separate from the strictly immutable, user-provided `documents/`. This will allow the agent to preserve synthesized knowledge, cheat sheets, or complex logic across sessions dynamically.

## Architecture

1.  **The Notebook Directory (`notes/`)**:
    *   Initialize an empty `notes/` folder in the project root.
    *   This is the *only* directory the agent will be allowed to modify text files in.
    
2.  **MCP Interaction Tools (`mcp_server.py`)**:
    We will create specific `@mcp.tool()` endpoints strictly sandboxed to the `notes/` folder so the agent can interact with its notebooks natively without needing heavy filesystem tools:
    *   `list_notes() -> str`: Returns all `.md` files present.
    *   `read_note(filename: str) -> str`: Loads a note's exact contents.
    *   `write_note(filename: str, content: str) -> str`: (Over)writes a markdown note.
    *   `append_note(filename: str, content: str) -> str`: Appends data to an existing note.

3.  **Semantic Auto-Ingestion (`memory/manager.py`)**:
    *   Just like the `documents/` folder, we will create a `sync_agent_notes()` method. The `mcp_server.py` will trigger this on startup so the agent's historical notes are chunked and automatically blended into its VectorRAG sub-conscious (tagged specifically as `{"source": "agent_notes/[filename]"}`).
    *   This means the agent won't even need to use `read_note` to recall old information; the semantic search will surface it implicitly!

4.  **Prompt Instructions (`skills.md`)**:
    *   Add a new Core Principle named `AGENT NOTES`. We will instruct the agent to utilize its `write_note` and `append_note` tools whenever it identifies a complex topic, a broad summary, or a long-term goal that it needs to "learn" and preserve.

## Open Questions

> [!WARNING]
> Please review and provide feedback:
> 1. To keep the agent fast, do you agree with restricting note-taking purely to Markdown (`.md`) format so it cleanly matches the ingestion pipeling?
> 2. Right now, `sync_agent_notes` will only inject notes into the semantic Vector database on **startup** (like `documents/`). If the agent writes a note *during* a session, it will have to explicitly use `read_note` to view it again until the application restarts. Is this acceptable, or do you want dynamic re-ingestion every time `write_note` is called?

## Execution Steps

1. **[NEW]** Process `mkdir notes`.
2. **[MODIFY]** `mcp_server.py` to add the four note-taking tools.
3. **[MODIFY]** `memory/manager.py` to add `sync_agent_notes`.
4. **[MODIFY]** `skills.md` to empower the LLM to write to this directory.
5. **[MODIFY]** Update `walkthrough.md` to document the new `notes/` system vs the `documents/` system!

## Verification
- We can ask the agent: "Please research Quantum Mechanics and write a summary into a new note called quantum.md".
- We verify the file generates correctly.
- Restart the agent and ask "What do you know about Quantum mechanics?" and ensure it auto-retrieves its own note from the vector database.
