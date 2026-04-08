# Implementation Plan: Replace LiteLLM with OpenAI SDK

You are partially correct! While `litellm` is technically a "wrapper" that can route to 100+ different proprietary APIs (like Anthropic Claude or Google Vertex), the **`openai` Python package is the undisputed industry standard**. 

Almost every local engine (including Ollama, LMStudio, and vLLM) natively provides an "OpenAI-Compatible Endpoint" (via `/v1`). By stripping out the `litellm` dependency and using the official `openai` package directly, we make the codebase lighter, standard-compliant, and much easier to debug because we remove an unnecessary middleman.

## Architecture

We will replace `litellm` with the official `openai` SDK (`from openai import OpenAI, AsyncOpenAI`).

1. **Environment Variables (`main.py`, `mcp_server.py`)**:
    * Transition from `LITELLM_MODEL` to `OPENAI_MODEL_NAME`.
    * Transition from `LITELLM_API_BASE` to `OPENAI_BASE_URL`.
    * **Critically**, the default Ollama base URL must change from `http://localhost:11434` to `http://localhost:11434/v1` so the OpenAI library recognizes the compatibility routing.

2. **Synchronous Client (`memory/manager.py`)**:
    * Initialize the sync `OpenAI` client in the constructor.
    * Refactor `completion(...)` to `client.chat.completions.create(...)` for Graph triplet and entity extraction.

3. **Asynchronous Client (`agent/react.py`)**:
    * Initialize the `AsyncOpenAI` client in the constructor.
    * Refactor `await acompletion(...)` to `await client.chat.completions.create(...)` for the main ReAct loop.

4. **Dependencies (`requirements.txt`)**:
    * Remove `litellm`, install `openai>=1.0.0`.

## Open Questions

> [!WARNING]
> Please review and provide feedback:
> 1. By switching to `openai`, we mandate that any model you target MUST expose an OpenAI-compatible `/v1/chat/completions` API structure. Ollama does this perfectly. Do you approve of this limitation in exchange for removing `litellm`?

## Execution Steps

1. **[MODIFY]** Update `requirements.txt` to remove `litellm` and add `openai`. Run `pip install`.
2. **[MODIFY]** Update `main.py` and `mcp_server.py` to use `OPENAI_` environment variables with `/v1` defaults.
3. **[MODIFY]** Refactor `manager.py` to utilize `OpenAI`.
4. **[MODIFY]** Refactor `agent/react.py` to utilize `AsyncOpenAI`.

## Verification
- Start the agent and confirm it connects correctly to Ollama via the OpenAI Python library without `litellm` crashing.
