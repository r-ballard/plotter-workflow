# Local Qwen coding pilot design

## Purpose

Establish whether the local Qwen3.8-27B deployment can complete a small plotter repository edit through a coding CLI, including file tools and checks, while frontier Codex plans and reviews the work. This is a workflow trial, not evidence of token or credit savings by itself.

## Scope and acceptance

The pilot adds a portrait preserve-layout regression case to `tests/test_preserved_physical_layout.py`. It checks that `build_vpype_command` omits geometry relayout and writer centering for an imposed portrait SVG and selects the portrait writer settings. The worker may edit only that test file. Production conversion code and the Task 6 findings are outside this pilot.

The pilot succeeds when the local worker makes the edit through its CLI tools, runs the focused test and Ruff, and returns a changed-file list, diff, command results, and unresolved questions. Frontier Codex independently reviews the diff and reruns the checks before integrating it. A failed baseline, missing dependency, shell-tool denial, or out-of-scope edit ends the local attempt for diagnosis rather than being silently accepted.

## Execution boundary

Use one isolated plotter worktree or branch at a recorded starting commit. Give Qwen the relevant function and test context, an exact task contract, and a narrow file allowlist. Run one local worker because the server has one slot. Keep model weights, logs, private prompts, and raw agent transcripts out of Git. Do not edit the frontier checkout concurrently with the worker.

First establish a healthy loopback service using the local-llm operator guide. Select a coding CLI that can perform an edit and shell checks against the service. The existing Codex CLI probe demonstrated transport but shell calls were denied; if that remains true, use another compatible CLI or report the blocked pilot. Do not treat a health check or function-call probe as a completed coding trial.

## Review and measurement

Record starting commit, elapsed time, local token usage when available, cloud usage from actual records when available, correction rounds, checks, and pass/fail outcome. Inspect the full diff for scope, correctness, portability, and unrelated changes. Compare the local trial with the cost of frontier planning and review; do not infer savings from raw model-token counts.

## Subsequent workflow

After a successful pilot, address Task 6's nested viewport translation and preserve-layout registration defects with failing integration tests before fixes. Run the focused and full suites, Ruff, and `git diff --check`, then obtain independent review. Only after Task 6 approval proceed to Task 7 and the final cross-repository validation described in `docs/logical-layer-plotter-handoff.md`.
