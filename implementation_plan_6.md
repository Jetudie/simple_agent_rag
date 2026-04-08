# Implementation Plan: Read-Only Mode & Memory Isolation

To add a toggle for the agent's learning capabilities and ensure the user's input cannot unintentionally (or maliciously) alter the agent's pristine knowledge base, we need to implement a formal **Read-Only Mode** and sever the automatic user ingestion pipeline.

## Architecture

1.  **Read-Only Switch (`mcp_server.py`)**:
    *   We will introduce an environment variable: `AGENT_LEARNING_ENABLED`.
    *   If this is set to `False`, the MCP server will effectively go into lockdown. The mutable tools (`memorize_fact`, `add_graph_edge`, `upsert_entity`, `delete_entity`, `delete_graph_node`, `write_note`, `append_note`) will gracefully return a standard observation: `"System Error: Agent Learning Mode is currently DISABLED. You cannot modify the memory databases."` instead of executing. This prevents the Agent from executing any writes.
    
2.  **Preventing User Alteration (`agent/react.py` & `mcp_server.py`)**:
    *   *Current State*: Every time you type a prompt, `react.py` automatically fires `add_user_memory(query)`, which blindly embeds your raw text permanently into the Agent's Vector and Graph database. 
    *   *The Fix*: We will rip this automatic ingestion step out of `react.py`. The agent will *only* remember what it is explicitly told to memorize via the formal `memorize_fact` tool (when learning is enabled) or from the `documents/` folder. This guarantees the user cannot passively poison the agent's memory just by talking to it.

## Open Questions

> [!WARNING]
> Please review and provide feedback:
> 1. By removing the automatic `add_user_memory(query)` pipeline, the Agent will no longer permanently remember what you whispered to it *last week* unless the Agent decides it was important enough to invoke `memorize_fact`. Do you agree that moving towards this strictly "Discretionary" memory model correctly solves the user-alteration problem?
> 2. How do you want to configure `AGENT_LEARNING_ENABLED`? Do you want me to code it to default to `False` (Read-only by default), or `True`?

## Execution Steps

1. **[MODIFY]** `main.py` and `mcp_server.py` to parse `AGENT_LEARNING_ENABLED` from `.env`.
2. **[MODIFY]** `mcp_server.py`'s mutation tools (`write_note`, `add_graph_edge`, etc.) to enforce the toggle boolean check.
3. **[MODIFY]** `agent/react.py` to delete the automatic `await self.mcp.call_tool("internal", "add_user_memory", ...)` invocation entirely.

## Verification
- Turn off Learning Mode. Ask the agent to "Please write a note".
- The agent should attempt to call `write_note` and receive the System Error explaining it is in Read-Only mode.
