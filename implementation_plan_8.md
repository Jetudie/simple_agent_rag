# Implementation Plan: Software Engineering Agent Tooling (SWE-Agent)

## Overview
This plan implements the critical toolchain required to elevate the agent from an autonomous reader to a full-fledged Software Engineering Agent, capable of targeted code search, code manipulation, and persistent terminal execution, all wrapped in rigorous file-system safety checks.

## Architecture Updates

### 1. Code Editing Restrictors
*   **Toggle**: We will introduce `WORKSPACE_ALLOWED_WRITE_DIRS` reading from the environment (defaulting strictly to: `"sandbox,notes,documents"`).
*   **Flexibility**: Because we dynamically split this variable, if you want the Agent to edit its own logic in the future, you simply update your `.env` to `WORKSPACE_ALLOWED_WRITE_DIRS=sandbox,notes,documents,agent,memory,tools` and restart the agent.
*   **Tools**: 
    - `write_new_file(path, content)`
    - `patch_file(path, search_string, replace_string)`: Replaces a specific string locally to safely edit code without LLM-truncation risk.

### 2. Semantic grep Search
*   **Tool**: `grep_codebase(regex_pattern: str, dir: str = ".")`
*   Instead of Vector searching paragraphs, this tool will iterate through directories matching raw Regex against `.py` or `.md` files. It natively respects the pre-existing `WORKSPACE_READ_ACCESS` toggle so it cannot scan secret files unless un-sandboxed.

### 3. Stateful Terminal Execution (Alternative Solution)
Running raw `subprocess.run` drops state immediately. True PTY/Daemon tracking on Windows is excessively bloated.
*   **The Stateful Workaround Solution**: We will implement a simulated stateful runner in the MCP server. We maintain a server-side `virtual_cwd` variable defaulting to your active project folder.
*   **Tool**: `run_command(command: str)`
*   **Logic**: If the LLM sends `cd memory`, our python backend catches the string, updates `virtual_cwd = os.path.join(virtual_cwd, "memory")`, and returns "Directory changed". If the LLM sends `dir` next, the script runs `subprocess.run("dir", cwd=virtual_cwd)`. 
*   This grants the LLM the illusion of a persistent shell session (it can traverse directories back and forth and run tests logically) without the massive architectural overhead of locking a live PTY daemon across the RPC protocol.

### 4. Prompt Instructions (`skills.md`)
*   Add rigid rules covering **CODE EDITING**, **TESTING (Terminal)**, and **GREP SEARCH**. Instruct the agent that after patching a file, it inherently must use `run_command` (like running tests or parsing syntax) to verify the patch did not break the framework.

## Execution Steps

1. Create a `sandbox/` directory.
2. Update `mcp_server.py` with `virtual_cwd` logic and the 4 new SWE tooling schemas.
3. Update `skills.md` to instruct the Agent on its new SWE capabilities.
4. Update `walkthrough.md` to formally document the SWE toolkit.
