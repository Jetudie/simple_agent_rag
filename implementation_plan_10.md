# Rolling Summary for Context Window

To ensure the agent does not lose its train of thought or forget past actions when the context window is garbage-collected, we will implement a **Rolling Conversation Summary Buffer** technique.

## Proposed Changes

### `agent/react.py`

- **Implement Summarization before Eviction**:
  Inside `_gc_context()`, before the pruned array of old messages are fully evicted, we will send an independent LLM prompt requesting a concise, dense summary of those specific pruned messages.
- **Inject Recursive Summary into Active Memory**:
  Instead of just telling the agent that messages were deleted, we will inject a new system message at `index 1` of the context window with the text: 
  > *"Observation: [Garbage Collection] Older messages were archived to 'diary/context_archive.md'. To retain your memory, here is a summary of the pruned context: \n\n[LLM_GENERATED_SUMMARY]"*
- **Rolling Memory Mechanism**:
  Because this new injected summary is securely at `index 1`, the *next* time Garabage Collection triggers (many loops later), the previous summary will be included in the new batch of evicted messages. This fundamentally forces the summarization engine to recursively compress the oldest history seamlessly into the newest history, maintaining an unbroken chain of long-term task-memory without blowing up the token count.
