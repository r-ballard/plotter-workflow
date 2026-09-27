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
