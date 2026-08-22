# Persistent Goal Agent

A small Python agent that keeps working toward file-defined targets until an independent verifier accepts
every pass criterion, or the configured loop/time limit is reached. It can use either an OpenAI-compatible
Chat Completions API or the OpenCode CLI and has no third-party Python dependencies.

## How the shift loop works

Each cycle has two deliberately isolated contexts:

1. A **fresh achievement worker** reads `AGENTS.md`, `GOALS.md`, `PASS_CRITERIA.md`, `HANDOVER.md`, and the
   latest `VERIFICATION_FEEDBACK.md`. It inspects and edits the workspace, runs checks, and returns a
   structured shift report.
2. A **fresh verification worker** receives no achievement conversation history. It gets the global prompt,
   targets, criteria, and handover claims, then independently inspects the workspace using read-only file
   tools and verification commands.
3. A pass ends the run. A failure is written to `VERIFICATION_FEEDBACK.md` and `HANDOVER.md`, then becomes
   input to the next new achievement context after the configured delay.
4. The orchestrator stops safely on full verification, `max_loops`, `max_time_seconds`, Ctrl+C, or a fatal
   API/configuration error.

Conversation transcripts and structured results are archived under `.goal_agent/runs/<run-id>/`. These logs
are for auditability; they are never copied into the next model context. `.goal_agent/latest-state.json`
contains the latest machine-readable run status.

## Configure

Python 3.11 or newer is required.

The project has no third-party runtime dependencies. For environments that use a conventional requirements
workflow, the intentionally empty `requirements.txt` can still be installed safely:

```bash
python -m pip install -r requirements.txt
```

1. Edit `AGENTS.md` with global instructions.
2. Put the desired outcomes in `GOALS.md`.
3. Put objective acceptance checks in `PASS_CRITERIA.md`.
4. Edit `config.toml` for the backend, model, loop count, delay, maximum total time, and tool limits.

### OpenAI-compatible API backend

Keep `backend.type = "api"` and set the API key. The supplied config reads it from `OPENAI_API_KEY`:

   ```powershell
   $env:OPENAI_API_KEY = "sk-your-key"
   ```

   Bash/zsh:

   ```bash
   export OPENAI_API_KEY="sk-your-key"
   ```

`base_url` may be a version root such as `https://api.openai.com/v1` or a full endpoint ending in
`/chat/completions`. `${NAME}` and `$NAME` environment references are supported in API string settings and
custom headers. To use a local provider without a meaningful key, configure whatever non-empty placeholder
that provider accepts directly in `config.toml`.

### OpenCode backend

Start OpenCode separately:

```bash
opencode serve --port 4096
```

Then select it in `config.toml`:

```toml
[backend]
type = "opencode"

[opencode]
executable = "opencode"
server_url = "http://localhost:4096"
# model = "provider/model"   # Omit to use the OpenCode default.
# agent = "build"            # Omit to use the OpenCode default.
# verifier_agent = "plan"    # Optional separate verifier agent.
timeout_seconds = 600
auto_approve = false
extra_args = []
```

No OpenAI-compatible URL or API key is required in this mode. Every phase uses a new `opencode run` command
with `--attach`, `--dir`, and any configured model or agent. The orchestrator never passes `--continue` or
`--session`, so achievement and verification remain separate OpenCode sessions. Authentication for the
models used by OpenCode remains OpenCode's responsibility.

The subprocess receives arguments as a list with `shell=False`; `shell=True` is unnecessary and would make
prompt contents vulnerable to shell interpretation.

`auto_approve = false` is the safer default. Configure OpenCode agent permissions appropriately or enable it
if unattended work would otherwise be denied. `extra_args` can hold additional documented `opencode run`
flags such as `["--variant", "high"]`.

## Run

Validate the setup without making an API request:

```bash
python run_agent.py --check-config
```

Start the persistent loop:

```bash
python run_agent.py
```

Or install an editable CLI command:

```bash
python -m pip install -e .
goal-agent
```

A successful run exits with code 0. Reaching a loop/time limit exits with code 1 while preserving a detailed
handover. Configuration, API, and fatal orchestration errors exit with code 2.

## Files and responsibilities

| File | Purpose |
|---|---|
| `AGENTS.md` | User-controlled global prompt, analogous to Codex CLI project guidance. |
| `config.toml` | Backend, API/OpenCode settings, loop/time controls, paths, and tool limits. |
| `GOALS.md` | Authoritative target list. |
| `PASS_CRITERIA.md` | Authoritative independent acceptance checks. |
| `HANDOVER.md` | Detailed durable shift notes: done, TODOs, tests, risks, verdict, and evidence. |
| `VERIFICATION_FEEDBACK.md` | Latest failed criteria and corrective work for the next achiever. |
| `.goal_agent/` | Per-run transcripts, structured results, and state (ignored by Git). |

The control files are re-read at the beginning of every cycle, so they can be refined between shifts.

## Tool safety

Model file operations are confined to the configured workspace root and reject path traversal. Verification
does not receive write/replace tools. Commands run with `shell=False`, an argument array, a timeout, and an
executable allow-list from `config.toml`. A command can still alter files or access resources available to
your account, so keep `allowed_commands` narrow and run the agent in a suitably isolated workspace.

The model cannot write the orchestrator's control files (`AGENTS.md`, goals, criteria, handover, feedback,
configuration, or `.goal_agent` state) through file tools. The orchestrator alone updates handover and
feedback. As with any coding agent, an allowed executable can itself modify files, so command permissions
remain a trust boundary.

Set `allow_commands = false` to disable command execution. File and command output is size-limited before it
is returned to the model.

These built-in tool restrictions apply to the API backend. In OpenCode mode, OpenCode supplies its own tools
and permission system; configure the selected OpenCode agents accordingly, especially the verifier agent.

## Tests

```bash
python -m unittest discover -s tests -v
```

The suite uses a fake API client; it requires no key and makes no network calls.
