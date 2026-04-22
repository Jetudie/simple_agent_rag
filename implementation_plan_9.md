# Context Window Garbage Collection (GC)

This change will implement a garbage collection mechanism for the agent's context window (`chat_history`) to prevent context overflow during long-running tasks.

## Proposed Changes

### `agent/react.py`

- **Add `_gc_context()` Method**:
  A new asynchronous method that inspects `self.chat_history`. If it exceeds 30 messages, it will:
  1. Slice out the old messages, keeping the `system` message (index 0) and the newest 12 messages.
  2. Format the pruned messages into markdown.
  3. Append the formatted text directly to an archive file (`diary/context_archive.md`).
  4. Inject a synthetic `user` message near the start of the newly pruned sliding window stating: *"Observation: [Garbage Collection] X older messages were removed from the context window to save tokens. They have been archived to 'diary/context_archive.md'."*
  5. Log the GC event to the MCP `log_diary_step`.

- **Trigger GC in the loop**:
  Invoke `await self._gc_context()` at the top of the internal ReAct loop (`for i in range(...)`) directly before calling `self.client.chat.completions.create(...)`. This ensures safety even during a very long `max_iterations` run.