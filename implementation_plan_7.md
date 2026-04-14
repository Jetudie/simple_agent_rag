# Implementation Plan: Agentic File Routing & Hierarchical Context

You are taking this system from a pure "RAG-Bot" straight into the "Coding Agent / Auto-SWE" realm! The "OpenClaw" or "Agentic Routing" methodology relies on the Agent dynamically exploring a repository using structural markers (like `AGENT.md`) rather than helplessly asking the user where things are.

## Architecture Updates

1.  **File System MCP Tools (`mcp_server.py`)**:
    *   We will add two new read-only tools to the MCP Server:
        *   `list_directory(path: str) -> str`: Lists files in a given directory safely. We will program it to automatically sniff out and highlight if an `AGENT.md` file exists in that specific folder so the LLM intuitively knows to read it!
        *   `read_source_file(path: str) -> str`: Reads the raw text of a file (with basic protection against `../` path traversal to keep it sandboxed to your workspace).
    
2.  **Structural Context Documents (`AGENT.md`)**:
    *   We will create a root `AGENT.md` file designed explicitly *for* the Agent. It will act as the "map of the world", explaining that `/agent` contains its brain, `/memory` contains its sub-conscious vector stores, and `/mcp_server.py` is its nervous system.
    
3.  **Skills Enhancement (`skills.md`)**:
    *   Add a new instruction block covering **HIERARCHICAL EXPLORATION**. We will instruct the LLM that whenever it is asked to inspect code or understand the repository, it should use `list_directory` hierarchically, specifically hunting for `AGENT.md` files as structural waypoints before diving into massive python scripts.

## What else is there room for improvement? (Next Steps)

If you are moving this towards an OpenClaw-style SWE Agent, you should eventually add:
1.  **Semantic Code Search (`grep_search`)**: The agent currently only has Vector Search over markdown files. Giving it a raw Regex/Grep tool over `.py` files would make it astronomically better at navigating large codebases.
2.  **Code Editing Tools (`patch_file` / `write_file`)**: Right now your agent can only take notes in `notes/`. If you want it to autonomously write code, we need tools that can replace specific line-ranges.
3.  **Terminal Execution (`run_command`)**: A true SWE agent can run `python -m pytest` or `npm run build` to verify its own code changes objectively before responding to you.

## Open Questions

> [!WARNING]
> Please review and provide feedback:
> 1. Since we previously put the system into a strict "Read-Only Mode" for memory integrity, are you okay with `list_directory` and `read_source_file` being able to read *any* file inside the project workspace (including `main.py` and `react.py`), or do you want them sandboxed purely to a specific folder?
> 2. Do you still want me to implement the `AUTO_BUILD_GRAPH` toggle from the previous conversation alongside this feature, or should we skip the graph toggle for now and purely focus on file routing?

## Execution Steps

1. **[NEW]** Create the root `AGENT.md` context file.
2. **[MODIFY]** Update `mcp_server.py` with `list_directory` and `read_source_file`.
3. **[MODIFY]** Update `skills.md` to instruct the Agent on Agentic File Routing.
