# Local Qwen pilot: configuration debrief

The low-risk pilot completed one test edit through OpenCode and the local Qwen
endpoint. The edit passed focused pytest, Ruff, independent review, and was
integrated as `418bd08`. The observed worker run took about 241 seconds, used
eight model rounds and nine tools, and reported 11,928 input, 2,534 output,
and 79,811 cached-read local tokens. No comparable cloud usage record was
captured, so this trial does not establish a cost saving.

## Changes needed for repeatable worker runs

| Setting or access | Pilot evidence | How to configure and verify |
| --- | --- | --- |
| Qwen context: 16,384 tokens | The 8,192-token server context was exhausted after the coding CLI supplied roughly 7,700 tokens of instructions. The edit completed after a restart at 16,384. | In `local-llm`, start `scripts/qwen38.ps1` with `-Action Start -Context 16384 -CpuFfn 20`; use `-Action Status` and verify the endpoint health before launching the worker. Set the coding CLI model context to the same value. Recheck actual GPU/CPU memory and throughput before increasing it again. |
| One worker slot | The deployment has one server slot. | Run one local coding session at a time. Queue bounded tasks; do not launch parallel local workers against this endpoint. |
| Worker worktree and temp writes | The worker successfully edited an isolated worktree, but Python temp writes were denied by the managed sandbox until an approved escalation. | Give the worker write permission to its specific worktree and a dedicated temp directory. Point `TEMP` and `TMP` to that directory for test runs. Verify by running focused pytest and Ruff without escalation. Keep integration in the orchestrator checkout. |
| Loopback model access | OpenCode reached the Qwen API at `127.0.0.1:8080/v1`. | Allow loopback traffic to that address and port for the worker CLI. Verify `/health`, then a read-only CLI tool call before assigning an edit. |
| Docker control | The managed sandbox denied Docker named-pipe access. An approved escalation was needed to restart the server. | Let the orchestrator start and stop the model service through a separately approved command. The worker needs only the loopback API. Verify `qwen38.ps1 -Action Status` and a health response. |
| Coding CLI tool policy | Nested Codex CLI reached the model but denied shell calls; OpenCode completed file and shell tool calls. | Keep OpenCode as the demonstrated worker CLI for now. Configure its OpenAI-compatible provider with base URL `http://127.0.0.1:8080/v1`, the pinned model ID, and context 16,384. Probe a read-only shell call before each new policy or CLI change. Treat Codex CLI as unproven until its nested command policy is diagnosed and an edit plus checks complete. |
| Git and hardware access | The worker needed neither commits nor serial-port access. | Let the worker produce a diff and test results only. The orchestrator reviews, commits, and handles physical plotting after preflight and operator confirmation. Do not grant Docker, `.git` write, or serial access to the worker merely to remove prompts. |

The worktree and Python environment used for this pilot are at
`.worktrees/qwen-pilot`; its OpenCode binary and local configuration are in
the ignored `.venv` directory. Reproduce these settings in a controlled user
or organization policy rather than committing machine-specific absolute paths
or model credentials to this repository. The host-managed sandbox profile may
need an administrator change; repository documentation alone cannot expand it.

For later trials, record the selected task, starting commit, allowed files,
elapsed time, local usage, actual cloud usage when available, correction
rounds, diff, and independent checks. Compare the whole workflow, including
orchestrator review and setup, before drawing a token-efficiency conclusion.

## Second trial: Task 7 resolved-pass validator

The next bounded task was to add a v2 resolved-pass-to-HP-GL validator and
three tests. The worker used an isolated `experiment/qwen-task7-sidecar`
worktree at `c48a77c`, the same OpenCode configuration, and a healthy
16,384-token Qwen service. Its baseline passed: 17 focused tests and Ruff.

The first worker attempt was stopped after about nine minutes with no edit.
Its trace contains five completed model rounds and 12 tool calls, including
successful baseline checks and source reads. Those completed rounds reported
12,163 input, 3,517 output, and 29,116 cached-read local tokens. One model
response hit the configured 2,048 output-token limit and OpenCode compacted
the session. A shorter continuation produced no tool call or edit before it
was stopped after several more minutes. The trace does not provide a completed
usage record for that interrupted continuation. The worker worktree remained
clean. No second-trial Qwen code was integrated.

This task exposed a workflow limit: reading a 48 KB module and navigating its
existing APIs consumed substantial local generation time before editing. For
the next trial, provide a smaller pre-extracted context and ask for a single
file change with an explicit time limit. Keep the full diff, tests, and
integration checks with the orchestrator. Do not infer a cloud token saving
from this incomplete attempt.

The reusable setup is now `opencode.qwen.json` plus
`docs/qwen-worker-guidance.md`. See `docs/qwen-worker-runbook.md` for the
asynchronous wait and two-strike procedure. The model configuration records
instructions and model limits; the orchestrator still enforces attempt count,
deadline, and diff scope.
