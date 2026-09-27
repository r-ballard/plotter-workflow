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
| Worker worktree and temp writes | The worker successfully edited an isolated worktree, but Python temp writes were denied by the managed sandbox until an approved escalation. | Follow [Worktree and temp writes](#worktree-and-temp-writes) below; set exact writable paths, direct `TEMP` and `TMP` to the dedicated temp directory, then run the write probe without escalation. |
| Loopback model access | OpenCode reached the Qwen API at `127.0.0.1:8080/v1`. | Allow loopback traffic to that address and port for the worker CLI. Verify `/health`, then a read-only CLI tool call before assigning an edit. |
| Docker control | The managed sandbox denied Docker named-pipe access. An approved escalation was needed to restart the server. | Follow [Docker control](#docker-control) below. A writable-root rule does not grant Windows named-pipe access. The simplest path is to start the service from a normal terminal and give the worker only the loopback API. |
| Coding CLI tool policy | Nested Codex CLI reached the model but denied shell calls; OpenCode completed file and shell tool calls. | Keep OpenCode as the demonstrated worker CLI for now. Configure its OpenAI-compatible provider with base URL `http://127.0.0.1:8080/v1`, the pinned model ID, and context 16,384. Probe a read-only shell call before each new policy or CLI change. Treat Codex CLI as unproven until its nested command policy is diagnosed and an edit plus checks complete. |
| Git and hardware access | The worker needed neither commits nor serial-port access. | Let the worker produce a diff and test results only. The orchestrator reviews, commits, and handles physical plotting after preflight and operator confirmation. Do not grant Docker, `.git` write, or serial access to the worker merely to remove prompts. |

## Worktree and temp writes

On this laptop, `C:\Users\hardcase\.codex\config.toml` currently selects
`[windows] sandbox = "unelevated"`. This chat also has a host-managed writable
root of `C:\Users\hardcase\Documents\developer\codex-repos\plotter-workflow`.
Changing your user config affects a **new** Codex CLI/IDE session when that
config is active; it may not override the managed profile already attached to
this chat. Check `/status` or `/permissions` in the new session before relying
on the change. Codex documents both the older `sandbox_workspace_write`
settings and newer permission profiles; [do not mix the two systems](https://learn.chatgpt.com/docs/permissions).

1. Create a dedicated temp directory in normal PowerShell:

   ```powershell
   $repo = 'C:\Users\hardcase\Documents\developer\codex-repos\plotter-workflow'
   New-Item -ItemType Directory -Force -Path "$repo\tmp\qwen-worker" | Out-Null
   ```

2. For a new CLI/IDE session using the older `workspace-write` settings, add
   these keys to `C:\Users\hardcase\.codex\config.toml`. Put top-level keys
   before any `[table]`; add the `writable_roots` entries to an existing
   `[sandbox_workspace_write]` table if one exists. Leave the existing
   `[windows] sandbox = "unelevated"` setting in place for this first probe:

   ```toml
   sandbox_mode = "workspace-write"
   approval_policy = "on-request"

   [sandbox_workspace_write]
   writable_roots = [
     'C:\Users\hardcase\Documents\developer\codex-repos\plotter-workflow\.worktrees',
     'C:\Users\hardcase\Documents\developer\codex-repos\plotter-workflow\tmp\qwen-worker',
   ]
   exclude_tmpdir_env_var = false

   ```

   The worktrees are already beneath the repository root, but the explicit
   entry makes their intended access clear for a separate worker checkout.
   The [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)
   defines `writable_roots` and temp-directory options. If the probe below
   still fails because the Windows sandbox cannot enforce the requested
   access, try the [preferred `elevated` Windows sandbox](https://learn.chatgpt.com/docs/windows/windows-sandbox)
   by changing the existing `[windows] sandbox` value to `"elevated"` in a
   new session. That setup may require administrator approval. If it is
   unavailable, keep `unelevated` and use an approved escalation for the
   specific failed command.

3. Before invoking OpenCode from the new session, set Python's temp location
   for that worker process:

   ```powershell
   $repo = 'C:\Users\hardcase\Documents\developer\codex-repos\plotter-workflow'
   $env:TEMP = "$repo\tmp\qwen-worker"
   $env:TMP = $env:TEMP
   $env:OPENCODE_CONFIG = "$repo\opencode.qwen.json"
   ```

4. Verify **without** an escalation in the new sandboxed Codex session.
   Replace `qwen-task7` with the chosen worker worktree name, then ask Codex
   to run this probe and the worker's focused pytest and Ruff commands:

   ```powershell
   $repo = 'C:\Users\hardcase\Documents\developer\codex-repos\plotter-workflow'
   $workerTree = Join-Path $repo '.worktrees\qwen-task7'
   $worktreeProbe = Join-Path $workerTree '.codex-write-probe'
   $tempProbe = Join-Path $env:TEMP 'codex-temp-probe.txt'
   'ok' | Set-Content -LiteralPath $worktreeProbe
   'ok' | Set-Content -LiteralPath $tempProbe
   Remove-Item -LiteralPath $worktreeProbe, $tempProbe
   ```

   If either write still fails, inspect the effective roots in `/status` or
   `/permissions`; a managed profile or Windows ACL may be overriding the
   user config. Do not interpret a successful escalated test as proof that
   ordinary worker writes are allowed.

## Docker control

The Qwen worker does not need the Docker API. Docker Desktop exposes a Windows
named pipe; adding a directory to `writable_roots` does not permit that pipe.
The least-drag setup is to start the server once from your normal PowerShell
session, outside Codex's sandbox, and leave it running across worker attempts:

```powershell
$localLlm = 'C:\Users\hardcase\Documents\developer\codex-repos\local-llm\.worktrees\local-coding-llm'
powershell -NoProfile -ExecutionPolicy Bypass -File "$localLlm\scripts\qwen38.ps1" -Action Start -Context 16384 -CpuFfn 20
powershell -NoProfile -ExecutionPolicy Bypass -File "$localLlm\scripts\qwen38.ps1" -Action Status
Invoke-RestMethod http://127.0.0.1:8080/health
```

Run `-Action Stop` with the same command when all trials are done. The
`-ExecutionPolicy Bypass` flag is scoped to that PowerShell process; the pilot
needed it because this machine's default script execution policy rejected the
`.ps1` file. The worker receives only `http://127.0.0.1:8080/v1`.

If the orchestrator must start or stop Docker itself, let it request an
**outside-sandbox approval for this exact script invocation**. For repeated
CLI sessions, a user-level [Codex execpolicy rule](https://learn.chatgpt.com/docs/agent-configuration/rules)
can allow an exact command prefix. This repo includes a tested, inactive
example at `docs/examples/qwen-docker.rules` that matches only the trusted
`qwen38.ps1` path and its `Start`, `Status`, and `Stop` actions. Review the
script first, then install the rule from normal PowerShell:

```powershell
$localLlm = 'C:\Users\hardcase\Documents\developer\codex-repos\local-llm\.worktrees\local-coding-llm'
$ruleDir = Join-Path $HOME '.codex\rules'
New-Item -ItemType Directory -Force -Path $ruleDir | Out-Null
Copy-Item 'docs\examples\qwen-docker.rules' (Join-Path $ruleDir 'qwen-docker.rules')
codex execpolicy check --pretty --rules (Join-Path $ruleDir 'qwen-docker.rules') -- powershell -NoProfile -ExecutionPolicy Bypass -File "$localLlm\scripts\qwen38.ps1" -Action Start -Context 16384 -CpuFfn 20
```

The check should report `"decision": "allow"`; a `Download` action or
direct `docker run` should show no matching rule. Restart Codex so it loads
the new rule. This rule only affects approved outside-sandbox command
execution; it does not expand filesystem roots or give the Qwen worker Docker
access. Use the exact `powershell` command form shown above so the prefix
matches. Organization-managed policy or auto-review may still require
approval regardless of a user-level rule.

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
