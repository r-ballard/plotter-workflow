# Running the local Qwen worker

This repository's `opencode.qwen.json` is an explicit OpenCode configuration
for the demonstrated local provider. It is not an automatic project default.
Run the model service with context 16,384, then set `OPENCODE_CONFIG` to this
file in the worker process. Keep one local worker at a time in its own Git
worktree. The server, OpenCode executable, Python environment, and log paths
are machine-specific and stay outside Git.

The task prompt must name the starting commit, allowed files, expected edit,
focused checks, Python path, `Attempt: 1 of 2`, and deliverables. Supply a few
relevant code excerpts or line ranges for a large module. The worker guidance
is loaded by the config; the task prompt still controls the file allowlist.

## Wait without token-heavy monitoring

Launch `opencode run --format json --pure` once, save the JSONL event stream
and process exit code in an ignored location, and wait for the process or a
deadline. In a Codex tool session, keep the returned session ID and make one
long `write_stdin` wait (up to the tool's five-minute limit) instead of polling
status every few seconds. The wait itself does not require reasoning about
each generated token. The orchestrator can do independent work while the local
process runs, then inspect the completed trace and diff once.

For an external PowerShell harness, launch the CLI with `Start-Process -PassThru
-WindowStyle Hidden` and redirected output, then use `Wait-Process -Id
<process-id> -Timeout <seconds>`. Use a configurable deadline, initially 30
minutes per attempt, rather than treating low tokens per second as failure.
The wait returns at exit or timeout. On timeout, stop the process, preserve
the trace, and count a strike. A separate watchdog may record heartbeat and
tool progress, but should not continuously involve the orchestrator model.

## Two attempts and review

1. Run attempt 1. If it completes with an in-scope diff and passing checks,
   review the diff and independently rerun checks. If it fails, record one
   strike and summarize the specific failure from the trace.
2. For attempt 2, give Qwen that feedback and narrow the prompt or context.
   State `Attempt: 2 of 2`. Use the same isolated worktree only after checking
   its diff; reset or create a fresh worktree if the first attempt left partial
   changes. Wait asynchronously again.
3. If attempt 2 fails, stop local retries and return the task to the
   orchestrator. Preserve elapsed time, completed-round token counts, tool
   counts, correction count, exit status, and changed files. Interrupted
   rounds may lack usage records; label those totals as incomplete.

The model config sets provider, context, output limit, and instructions. The
orchestrator or external harness must enforce deadlines, attempt counts, and
the worktree allowlist. OpenCode instructions alone cannot enforce them.
