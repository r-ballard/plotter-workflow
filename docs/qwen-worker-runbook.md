# Running the local Qwen worker for plotter tasks

The canonical config, instructions, and watchdog live in the sibling
`local-llm` repository's `local-coding-llm` worktree:

- `config/opencode.qwen.json`
- `docs/qwen-worker-guidance.md`
- `docs/qwen-worker-watchdog.md`
- `scripts/qwen_worker_watchdog.py`

Start the Qwen server with context 16,384 and confirm `/health` is `ok`.
Prepare an isolated, clean plotter worktree and a task spec outside that
worktree. The spec names the OpenCode executable, the canonical model config,
the task prompt, an exact file allowlist, independent checks, and an output
directory outside the worktree. Follow `local-llm/docs/qwen-worker-watchdog.md`
for the full spec and command.

The watchdog waits on the worker process without model-side polling. It
permits one corrective retry, stops immediately for an out-of-scope edit,
enforces an elapsed deadline, and writes JSONL logs plus a benchmark summary.
The frontier orchestrator reviews the completed diff and reruns checks before
integrating it. The configuration and sandbox setup findings remain in
`docs/qwen-pilot-configuration-debrief.md` in this repository.

## Preparing the next bounded task

The third trial spent two full attempts reading files without an edit. Give the
worker a self-contained brief so its first useful action can be a write:

1. Name one allowed output file and a concrete acceptance check. Include a
   short destination skeleton or the exact function/section to change.
2. Supply the required source facts or narrow excerpts in the prompt. Name
   at most a few optional files and exact line ranges for verification. Do not
   ask the worker to rediscover the repo, reread a long guide, or run a broad
   baseline for a documentation-only task.
3. Instruct it to make the first small edit after one short verification pass,
   then run only the focused check. If a fact remains uncertain, it should
   report the uncertainty rather than continue searching indefinitely.
4. Keep the watchdog's asynchronous process wait and two attempts. Set a
   task-sized elapsed deadline; do not extend the 30-minute default solely
   because local token generation is slow. Review the trace for visible
   progress before granting more time.

Prompt shape for a single-file task:

```text
Starting commit: <sha>. Edit only <relative path>. Do not commit.
Goal: <one reviewable change>.
Use these verified facts: <short facts or excerpts>.
Optional verification reads: <file:line-range>, <file:line-range>.
Create the first draft before further repository exploration.
Run: <one focused check>. Report changed files, result, and uncertainty.
```

Before a long trial, run a tiny direct OpenCode probe that creates a temporary
file inside the *same worker worktree* and under the same OpenCode config.
Inspect the file, then remove it before starting the watchdog, which requires
a clean worktree and an in-scope diff to count an attempt as successful.
The successful shell write probe from the orchestrator checks filesystem
access, but does not prove OpenCode's own tool permissions. Do not reuse the
failed documentation task as that probe.

The current watchdog has an elapsed deadline, not a no-edit or tool-round
deadline. Until that guard is implemented, use a shorter first-attempt timeout
for small tasks and inspect its completed trace once after it exits. A future
watchdog revision should stop an attempt after a configurable number of
successful read/search tool calls without an in-scope diff, then pass that
specific feedback to attempt two. The watchdog, rather than the orchestrator
model, should do this monitoring.

The local-llm watchdog also accepts `max_agent_steps` for a per-task OpenCode
build-agent round limit and redirects OpenCode's XDG data, cache, config, and
state paths under the run output directory. The fourth trial edited early but
timed out after its diff check. Review its completed tool calls and diff before
discarding a timed-out attempt. A redirected-path probe still hit the managed
sandbox's nested `git` process restriction, so an approved launch is currently
required. See the fourth-trial metrics in the debrief.
