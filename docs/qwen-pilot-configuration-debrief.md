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
| Qwen context: 65,536-token tested default | The 8,192-token pilot exhausted context; later 16,384-token runs compacted or timed out. Trials at 24,576 and 65,536 completed without compaction. | In `local-llm`, `scripts/qwen38.ps1 -Action Start` now defaults to `-Context 65536 -CpuFfn 28`, and `config/opencode.qwen.json` advertises 65,536. Keep server and client limits aligned; verify `/health` and GPU headroom. See the trial data below before increasing it again. |
| One worker slot | The deployment has one server slot. | Run one local coding session at a time. Queue bounded tasks; do not launch parallel local workers against this endpoint. |
| Worker worktree and temp writes | The worker successfully edited an isolated worktree, but Python temp writes were denied by the managed sandbox until an approved escalation. | Follow [Worktree and temp writes](#worktree-and-temp-writes) below; set exact writable paths, direct `TEMP` and `TMP` to the dedicated temp directory, then run the write probe without escalation. |
| Loopback model access | OpenCode reached the Qwen API at `127.0.0.1:8080/v1`. | Allow loopback traffic to that address and port for the worker CLI. Verify `/health`, then a read-only CLI tool call before assigning an edit. |
| Docker control | The managed sandbox denied Docker named-pipe access. An approved escalation was needed to restart the server. | Follow [Docker control](#docker-control) below. A writable-root rule does not grant Windows named-pipe access. The simplest path is to start the service from a normal terminal and give the worker only the loopback API. |
| Coding CLI tool policy | Nested Codex CLI reached the model but denied shell calls; OpenCode completed file and shell tool calls. | Keep OpenCode as the demonstrated worker CLI for now. Configure its OpenAI-compatible provider with base URL `http://127.0.0.1:8080/v1`, the pinned model ID, and context 65,536. Probe a read-only shell call before each new policy or CLI change. Treat Codex CLI as unproven until its nested command policy is diagnosed and an edit plus checks complete. |
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
   $localLlm = 'C:\Users\hardcase\Documents\developer\codex-repos\local-llm\.worktrees\local-coding-llm'
   $env:OPENCODE_CONFIG = "$localLlm\config\opencode.qwen.json"
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

The canonical reusable setup now lives in the `local-llm` worktree:
`config/opencode.qwen.json`, `docs/qwen-worker-guidance.md`, and
`scripts/qwen_worker_watchdog.py`. Its `docs/qwen-worker-watchdog.md` gives the
task-spec format and run procedure. The watchdog enforces the two-attempt
deadline and diff checks without model-side polling; the frontier orchestrator
still reviews each proposed integration.

## Third trial: neutral plotting operator guide

The worker received a bounded, single-file documentation task in the isolated
`experiment/qwen-task7-guide` worktree at `f81ee4f`. Its allowed output was
`docs/how-to/neutral-logical-layer-plotting.md`. The watchdog waited on the
worker process asynchronously and enforced two 1,800-second deadlines.

| Attempt | Elapsed | Completed rounds | Tools | Input | Output | Cached read | Diff |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 1,800.73 s | 16 | 28 | 58,768 | 19,174 | 103,155 | none |
| 2 | 1,800.44 s | 17 | 29 | 53,706 | 19,543 | 113,654 | none |
| Total | 3,601.17 s | 33 | 57 | 112,474 | 38,717 | 216,809 | none |

The trace's tool calls were reads, searches, and shell inspections; there was
no write or patch call in either attempt. Both attempts timed out, and the
worker worktree remained clean. Local token counts cover completed model
rounds only; interrupted final rounds and cloud usage were not measured.
The task produced no Qwen change to integrate. The orchestrator completed the
guide in the plotter branch and checked it against the current CLIs.

This run shows a concrete efficiency limit: asynchronous waiting prevented
frontier model polling, but it did not prevent a local worker from spending an
hour navigating context without producing a diff. For the next Qwen task,
prepare the exact source excerpts and destination skeleton in the prompt,
require an early first edit, and cap unproductive read/tool rounds in the
external watchdog. Keep the two-strike correction loop and independent review;
measure setup, review, and correction effort as well as local usage before
claiming a workflow saving.

### Direct OpenCode write probe after the third trial

An orchestrator shell probe had already written to the worker worktree. A
separate direct OpenCode probe now confirms the worker's own write tool can do
so: with the same OpenCode config and `experiment/qwen-task7-guide` worktree,
Qwen made one completed `write` tool call, created
`docs/how-to/qwen-write-probe.txt` with the requested content, and exited 0.
The content was verified and the probe file removed; the worktree is clean.
This rules out an OpenCode file-write denial as the explanation for the third
trial's no-edit result.

The first, sandboxed probe launch failed before reaching Qwen because OpenCode
could not open `C:\Users\hardcase\.local\share\opencode\log\opencode.log`.
The approved outside-sandbox launch succeeded. This is a launcher log-path
permission issue, separate from worker worktree writes. Use the approved
launch path until OpenCode's state and log directories are placed in a writable
location and verified with an unapproved probe; a shell write probe alone does
not check this boundary. A later unapproved OpenCode probe with redirected
`XDG_*` paths passed the log-path barrier but failed at
`EPERM: operation not permitted, uv_spawn 'git'`. The managed sandbox still
requires an approved launch for OpenCode's nested Git process.

## Fourth trial: v2 pen-plan documentation

The next brief supplied all schema and resolver facts up front and asked for
one section in `docs/reference/pen-plan.md`, with an early first edit and no broad search.
Qwen edited the allowed file about 306 seconds into attempt 1 and ran
`git diff --check` about 630 seconds in. The watchdog nevertheless timed out
at the 720-second deadline. Attempt 2 made a further in-scope edit and ran the
same check, then also timed out. Neither attempt returned a clean completed
session, so the watchdog correctly reported failure and ran no independent
checks. The orchestrator reviewed the diff, corrected one accounting sentence,
and verified that the embedded JSON matches the checked-in v2 example.

| Attempt | Elapsed | Completed rounds | Tools | Input | Output | Cached read | Diff |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 720.48 s | 4 | 3 | 19,874 | 5,851 | 16,917 | `docs/reference/pen-plan.md` |
| 2 | 720.47 s | 8 | 6 | 11,393 | 5,906 | 70,542 | `docs/reference/pen-plan.md` |
| Total | 1,440.95 s | 12 | 9 | 31,267 | 11,757 | 87,459 | one usable section |

The first attempt proves that a smaller, fact-rich brief can prompt an edit.
The timeout after edit and checks remains a separate termination problem.
One completed model round ended with reason `length` at exactly the configured
3,072 output-token limit. That is evidence to test the cap, not proof that it
caused both hangs: the edit and check completed, and several other rounds
ended normally. Local usage excludes interrupted final rounds; cloud usage
was not measured.

The [local-agent tuning study](https://doug.sh/posts/tuning-a-local-coding-agent-oh-my-pi/)
reports that reply limits covering reasoning and file-write text can truncate
tool calls in Oh My Pi, while oversized tool output and cache misses slow
prefill. Its 32,768 reply limit and 262,144 context were measured on a
different server and agent. Our OpenCode config currently advertises 16,384
context and 3,072 output; test a moderate output increase only with a matching
server context and inspect response finish reasons, completed edits, and time
to first token before adopting it.

The canonical `local-llm` watchdog now redirects OpenCode state and logs to
the run output directory and accepts an optional `max_agent_steps` setting
for OpenCode's build agent (`133801a`). Eight offline tests and Ruff pass.
An agent-step limit bounds completed agent rounds, but a wall-clock deadline
is still needed for a single slow reply. At that trial there was no no-edit
guard; a later watchdog revision adds an optional first-edit deadline.

## Fifth trial: output-limit comparison

To isolate the reply-cap hypothesis, the worker repeated the fourth trial's
prompt, checks, starting commit (`68a9099`), 16,384-token server context, and
720-second attempt deadline in a fresh worktree. The tested model setting was
OpenCode's advertised `limit.output`, changed from 3,072 to 6,144. The watchdog
also used its newer XDG state-path isolation, so this is a close comparison,
not a perfectly identical replay. The canonical model config remains at 3,072
pending evidence of a benefit.

| Attempt | Elapsed | Completed rounds | Tools | Input | Output | Cached read | Diff |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 720.59 s | 3 | 2 | 14,153 | 5,678 | 8,787 | none |
| 2 | 720.47 s | 6 | 6 | 7,869 | 4,153 | 43,959 | `docs/reference/pen-plan.md` |
| Total | 1,441.06 s | 9 | 8 | 22,022 | 9,831 | 52,746 | one draft |

No completed response reached the 6,144-token cap; neither attempt exited before
its deadline. Attempt 1 had no edit. Attempt 2 edited at about 401 seconds,
but its draft repeated the incorrect claim that every catalog layer is
assigned exactly once, despite its own repeated-layer example. The already
reviewed fourth-trial section remains authoritative; no fifth-trial edit was
integrated. This comparison does not support raising the output cap
as a resolution to the timeout. It does not rule out a cap effect on larger
file writes or other tasks. Interrupted final rounds and cloud usage remain
unmeasured.

The local-llm watchdog now treats a timed-out, in-scope diff that passes its
independent checks as `REVIEW` and stops before a second attempt (`f227e60`).
It returns a nonzero exit code and still requires orchestrator review; a
partial OpenCode session is never labeled `PASS`. Nine offline tests and Ruff
passed. That change would have avoided a second full attempt in the fourth
trial, while preserving the chance to catch the accounting error in review.

## Next tuning test: compaction pressure and clean completion

The first low-risk pilot exited cleanly after its edit. Later behavior is more
specific than “no output”: trial 4 edited in both attempts, and trial 5 edited
in attempt 2, but OpenCode did not exit before the deadline. A trace audit of
the four trial-4 and trial-5 attempts found one synthetic
`compaction_continue` event in **each** attempt. In trial 4 attempt 2, Qwen
also emitted a short “Done” message before OpenCode started another step.
The earlier guide trial had five such continuations per attempt. This points
to context/compaction overhead as a stronger next hypothesis than the reply
cap, but the traces alone do not prove the cause of the final slow step.

The tested OpenCode CLI is 1.18.32. Its
[v1 configuration reference](https://opencode.ai/docs/config/#compaction)
documents automatic compaction and shows a 10,000-token `reserved` buffer in
its example; we have not measured the effective default in this installation.
With the currently advertised 16,384-token context, a large reserve would
leave a narrow working budget. The next controlled trial should repeat the
same short task at 16,384 context and 3,072 output, changing only
`compaction.reserved` to 4,096 in a temporary per-run config. Do not also
change model, prompt, output cap, or agent-step limit in that trial. Compare
time to first edit, compaction events, response finish reasons, clean process
exit, and the watchdog's independent checks. Keep the original config if the
smaller reserve causes context errors or no completion improvement.

If compaction still occurs early, measure whether a 24,576 or 32,768-token
server context fits the machine and improves a matched run before changing
the canonical deployment. Once a clean baseline exists, test
`max_agent_steps` separately to limit extra post-edit rounds. Do not infer
support for the article's vLLM thinking budget from this llama.cpp endpoint;
verify the server's accepted request fields before testing that setting.

## Sixth trial: smaller compaction reserve

The worker repeated the v2 documentation task from `68a9099` in a fresh
worktree at 16,384 server/client context and 3,072 output. The temporary
OpenCode 1.18.32 config set `compaction.auto: true` and
`compaction.reserved: 4096`; the canonical config was unchanged. The prompt,
independent checks, and 720-second attempt deadline matched the earlier task.
The watchdog was newer (`f227e60`), so the retry behavior changed: a timed-out
in-scope diff with passing checks returned `REVIEW` after one attempt.

| Elapsed | First edit | Completed rounds | Tools | Input | Output | Cached read | Compactions |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 720.53 s | ~247 s | 5 | 3 | 23,118 | 7,259 | 16,920 | 2 |

Qwen edited the allowed file, ran `git diff --check`, and both watchdog checks
passed. OpenCode still did not exit before the deadline. One completed reply
ended at the 3,072 output limit, and the trace has two synthetic
`compaction_continue` events at about 511 and 649 seconds. The smaller reserve
did not remove compaction or solve clean completion. It may have moved the
first edit earlier than in trials 4 and 5, but one nondeterministic run is not
enough to claim a timing improvement. Interrupted final-round and cloud usage
were not measured.

Orchestrator review rejected the draft despite the two passing checks. It
incorrectly said every catalog ID is assigned exactly once while permitting
repeated layers, and its resolved sidecar filename examples omitted the pass
ID. The existing reviewed section remains authoritative. This demonstrates
that `REVIEW` means only an in-scope, mechanically checked diff; for document
tasks, add an independent check of parsed examples and exact artifact names
when available, then still review the prose against the implementation.

## Seventh and eighth trials: more context

The same v2 documentation task from `68a9099` was replayed in fresh
worktrees with matching server and client context. Output stayed at 3,072,
the default compaction settings were used, and each attempt had a 720-second
deadline. These trials changed both context and CPU FFN offload to fit GPU
memory, so elapsed time does not isolate context size.

| Trial | Context | CPU FFN | Result | Elapsed | First edit | Rounds | Tools | Input | Output | Cached read | Compactions |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 7 | 24,576 | 20 | PASS, attempt 1 | 205.95 s | ~148 s | 4 | 3 | 12,489 | 1,806 | 36,923 | 0 |
| 8 | 65,536 | 28 | PASS, attempt 1 | 354.81 s | ~267 s | 6 | 5 | 10,347 | 2,575 | 53,909 | 0 |

Trial 7 had about 610 MiB GPU memory free after loading. Trial 8 had about
1,918 MiB free after loading and 1,596 MiB after the task. Its server log
reported roughly 8–9 generated tokens/second across completed rounds. Both
workers edited and exited cleanly without compaction. The 65k run was slower
end to end, but had more completed model output and tool activity, plus more
weights offloaded to CPU. It is not a controlled tokens/second comparison.

Both drafts were benchmark artifacts: the reviewed section from trial 4 was
already integrated. The 65k draft repeated an incorrect statement that every
catalog ID must be assigned exactly once. Inspection found that the benchmark
prompt itself said “assigned once” and then allowed cross-pass reuse. That
contradiction can contaminate quality comparisons. The next prompt must say
that an assigned ID appears in one pass **unless** it is listed in
`repeated_layers`, in which case it appears in at least two passes.

The [16 GB Qwen guide](https://www.reddit.com/r/LocalLLM/comments/1vq5oyu/guide_for_running_dense_models_on_16_gb_vram_qwen/)
uses a 140,000-token runtime context with different offload, operating-system,
and GPU conditions. The [model card](https://huggingface.co/unsloth/Qwen3.8-27B-GGUF)
states a larger native context. Neither number proves that 140k fits this
Windows setup. Configured context reserves KV memory, while the cost of
generation also depends on how much of that context is actually filled.

The tested 65,536 context / 28 CPU FFN pair is now the default in the
`local-llm` server script and OpenCode config (`0a47996`). The 3,072 output
limit stays unchanged. The next trial tested 131,072 context as a per-task
override and recorded service health, GPU headroom, compaction, first edit,
completion, and review quality.

## Ninth trial: 131,072 context

A fresh worktree at `68a9099` used matching 131,072 server/client context,
34 CPU FFN layers, the same 3,072 output cap, default compaction settings,
and a corrected version of the v2 task prompt. The corrected prompt states
that an assigned catalog ID appears in one pass unless declared in
`repeated_layers`. This is a new prompt variable, so the run is a capacity
and workflow check, not a strict speed comparison with trials 7 and 8.

| Result | Elapsed | First edit | Rounds | Tools | Input | Output | Cached read | Compactions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| PASS, attempt 1 | 514.72 s | ~401 s | 6 | 5 | 11,327 | 3,469 | 59,136 | 0 |

The model loaded with about 1,413 MiB GPU memory free; after the task it
had only 651 MiB free. Completed server rounds reported roughly 5–8 generated
tokens/second. The worker exited cleanly and its accounting prose was correct.
However, its generated output named generic `<svg-stem>.resolved.penplan.json`
and `<svg-stem>.placement.json` sidecars. The implementation derives each
sidecar from the **per-pass HP-GL path**, so the pass ID belongs in those
filenames. The watchdog's broad text check did not catch this error, and the
draft was not integrated. The task prompt also described the sidecars only as
“adjacent”; future briefs should give exact per-pass names and include an
independent check for them.

The 131k setting is feasible for this run, but its smaller GPU margin and
slower observed generation do not justify replacing the successful 65k
default for short tasks. Use 131k as a per-task override when the prompt and
expected trace need it; measure memory again after changing display load or
model settings. The 65k service was restored after the benchmark.

## Tenth trial: useful plotter documentation task at the 65k default

With the tested 65,536 server/client context and 3,072 output cap, Qwen was
assigned a narrow correction to two existing plotter documents. The brief
gave the converter's exact per-pass sidecar naming rule and allowed edits only
to `docs/reference/pen-plan.md` and the neutral logical-layer operator guide. The watchdog
used a 600-second deadline and checked whitespace plus exact filename examples.

| Outcome | Elapsed | First edit | Rounds | Tools | Input | Output | Cached read | Compactions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| REVIEW, attempt 1 | 600.56 s | ~421 s | 8 | 10 | 20,115 | 4,364 | 115,138 | 0 |

Both in-scope documents were edited and both independent checks passed, but
OpenCode did not exit before the deadline. The watchdog therefore returned
`REVIEW` and skipped the corrective retry. The orchestrator checked the diff
against `pen_plan.py` and `dpx3300_convert.py`, reapplied it to the main
branch, and reran the checks. The prose now states that the HP-GL file and
both sidecars carry the pass ID. This was useful worker output despite the
termination failure. The trace shows several extra reads and searches before
the first edit despite the narrow brief, so first-edit latency remains an
optimization target; no model-side polling was used.

The operator-provided `viz_virtualserver` clone allowed the separate
`generative-viz-workspace` bootstrap and verifier to complete. Both
repository environments now use the pinned uv/Python toolchain. The viz
repository passed 483 tests and Ruff; plotter passed 405 tests and Ruff after
running pytest with filesystem access for temporary fixtures. Physical
plotter validation remains open.

## Eleventh trial: end-to-end handoff note

After the cross-repository neutral bundle converted and preflighted in two
passes, the default 65k worker was given a one-file handoff note. The brief
supplied all observed facts and a 600-second attempt deadline. Attempt 1
timed out without an edit: its visible trace had two completed rounds, one
tool, 9,649 input and 3,158 output tokens. The watchdog began attempt 2;
that trace reached its first edit at about 90 seconds and had three completed
rounds, three tools, 1,161 input and 786 output tokens when the orchestrator
interrupted it. The second draft was in scope but 21 lines long, introduced a
spacing error in existing prose, and had not produced a final watchdog result.
The orchestrator wrote a shorter note from the independently verified
artifacts instead. Interrupted-round usage and cloud usage were not measured.

This trial reinforces the need for a no-edit guard: a fact-rich, one-file task
can still spend a full deadline before making its first edit. Stopping a
corrective attempt after a reviewable edit saved another possible full
deadline, but it means this trial cannot be reported as a watchdog `PASS` or
`REVIEW` outcome.

The `local-llm` watchdog now implements an optional
`first_edit_timeout_seconds` setting (`f123115`). It waits until that
deadline without model calls, checks for a tracked or untracked diff, and
stops a no-edit attempt with specific feedback for the second attempt. It
preserves the full wall deadline after an early edit. Twelve offline tests
and Ruff passed. The change has not yet been exercised in a live Qwen task;
480 seconds is the provisional first-edit limit for a 600-second documentation
task, based on the observed successful first-edit times above.

## Twelfth trial: booklet manifest guide with the guard enabled

The default 65,536-context worker added a software-only `booklet.json`
example to the neutral plotting guide. The task allowed one file, supplied
the exact eight-page source order used by the successful integration run,
and set a 600-second wall deadline plus a 480-second first-edit deadline.

| Outcome | Elapsed | First edit | Rounds | Tools | Input | Output | Cached read | Compactions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| PASS, attempt 1 | 337.97 s | ~257 s | 6 | 5 | 11,155 | 2,481 | 53,317 | 0 |

The worker exited cleanly. The watchdog's JSON check parsed the full manifest
and verified page numbers and source order; the orchestrator independently
compared it with the manifest used in the successful software-only run. The
first-edit deadline was enabled but did not fire, so this live trial verifies
normal completion with the guard configured, not the live early-stop path.
The diff was reviewed and integrated. Cloud usage was not measured.

## Thirteenth trial: pytest collection scope

Bare `pytest --collect-only -q` in the main plotter checkout found 405 tests
but then failed on access-denied ignored `tmp` directories. Explicit
`pytest tests -q` avoided those directories. The project had `pythonpath`
configured but no pytest collection root; `.gitignore` does not control
pytest's default recursion. Qwen was given the one-line `pyproject.toml`
change `testpaths = ["tests"]`, a 600-second wall deadline, and a 300-second
first-edit deadline.

| Outcome | Elapsed | First edit | Rounds | Tools | Input | Output | Cached read | Compactions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| PASS, attempt 1 | 128.01 s | ~26 s | 4 | 3 | 8,821 | 449 | 26,675 | 0 |

The worker exited cleanly and independent checks confirmed the TOML value
and 405 collected tests. After integration, the original main checkout also
collected 405 tests without traversing `tmp`; bare pytest passed 405 tests
with fixture-write access, and Ruff passed. The managed sandbox can still
deny pytest's temporary fixture writes; collection scope does not grant that
permission. The first-edit guard was enabled but did not fire. Cloud usage
was not measured.
