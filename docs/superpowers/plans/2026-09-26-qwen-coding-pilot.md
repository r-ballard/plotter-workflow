# Local Qwen Coding Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove that the loopback Qwen worker can make and check one bounded plotter repository edit through a coding CLI.

**Architecture:** Frontier Codex prepares an isolated worktree and exact task contract. One local worker edits a single test file; frontier Codex checks the diff and independently runs the same checks before integration.

**Tech Stack:** PowerShell, Git, Python 3.11–3.13, pytest, Ruff, local llama.cpp OpenAI-compatible endpoint, a tool-capable coding CLI.

**Spec:** `docs/superpowers/specs/2026-09-26-qwen-pilot-design.md`

## Global Constraints

- Worker edit allowlist: `tests/test_preserved_physical_layout.py` only.
- Keep production conversion code, Task 6 fixes, model weights, logs, private prompts, and raw transcripts outside the pilot diff.
- One local Qwen worker at a time; record the starting commit.
- A health check or tool-call probe does not count as a completed edit.
- If the baseline fails, shell tools are denied, or the worker changes an unallowed file, stop and report the trial outcome.

## Review Focus

- Portrait metadata with `landscape=False` must preserve physical coordinates and omit `--landscape`.
- The test must exercise `build_vpype_command` itself, not merely inspect metadata.
- The worker's actual diff must contain only the allowed test file.
- Tests or Ruff unavailable in the worker environment must be reported, not called passing.
- A successful local edit must still pass an independent frontier review and rerun.

---

### Task 1: Prepare the isolated worker environment

**Files:**
- Read: `docs/superpowers/specs/2026-09-26-qwen-pilot-design.md`
- Read: `tests/test_preserved_physical_layout.py`
- Read: `dpx3300_convert.py`
- Create outside Git: local worktree and temporary trial notes

**Interfaces:**
- Consumes: current `feat/logical-layer-plotter` commit.
- Produces: worker worktree path, starting commit, healthy Qwen endpoint, executable Python checks, and a coding CLI with working file and shell tools.

- [ ] **Step 1: Record `git rev-parse HEAD` and create a dedicated worktree/branch from it.** Keep the frontier checkout untouched while the worker edits.
- [ ] **Step 2: Establish the Python baseline.** In the worker worktree run `python -m pytest tests/test_preserved_physical_layout.py -q` and `python -m ruff check tests/test_preserved_physical_layout.py`. If the tools are absent, provision the repository's declared dev dependencies, then rerun; stop if a clean baseline cannot be obtained.
- [ ] **Step 3: Start and verify the local service.** Follow the pinned `local-llm` operator guide: `qwen38.ps1 -Action Start -Context 8192 -CpuFfn 20`, then `-Action Status` until healthy. Record startup result without committing logs.
- [ ] **Step 4: Verify coding CLI tool access.** Prefer an already installed compatible CLI. Test a read-only file command in the isolated worktree; if the documented Codex CLI policy block recurs, try a compatible local CLI such as OpenCode. Stop if no CLI can use file and shell tools. Record the chosen CLI and version.

### Task 2: Local worker adds the portrait regression case

**Files:**
- Modify: `tests/test_preserved_physical_layout.py`
- Test: `tests/test_preserved_physical_layout.py`

**Interfaces:**
- Consumes: the worktree, starting commit, and verified CLI from Task 1.
- Produces: one new test method and worker report; no production-code changes.

- [ ] **Step 1: Give Qwen this contract.** Task: add `test_imposed_portrait_svg_preserves_layout_without_landscape` in `PreservedPhysicalLayoutTests`. Allowed file: `tests/test_preserved_physical_layout.py`. Create a temporary SVG with preserve metadata, page size `letter`, orientation `portrait`; call `build_vpype_command` with `landscape=False`, `page_size="letter"`, `device_page_size="letter_lower_left"`, and the same remaining arguments as `_command`. Assert that `layout`, `--fit-to-margins`, `--center`, and `--landscape` are absent, while `write`, `letter_lower_left`, and `--absolute` are present. Stop on ambiguity, failing baseline, missing dependency, or edits outside the allowlist. Deliver summary, changed files, diff, checks with results, and questions.
- [ ] **Step 2: Have the worker edit through its CLI and run** `python -m pytest tests/test_preserved_physical_layout.py -q` and `python -m ruff check tests/test_preserved_physical_layout.py`. Expected: both pass; capture command results and local usage if the CLI exposes it.
- [ ] **Step 3: Collect** `git status --short`, `git diff -- tests/test_preserved_physical_layout.py`, elapsed time, correction rounds, and available usage records. The worker does not commit or merge.

### Task 3: Frontier review and integration decision

**Files:**
- Review: `tests/test_preserved_physical_layout.py`
- Record outside Git: trial measurements and outcome

**Interfaces:**
- Consumes: Task 2 diff and report.
- Produces: accepted pilot commit or a documented failed trial with no partial integration.

- [ ] **Step 1: Review the entire worktree diff and changed-file list.** Confirm the portrait assertions match the spec, no production behavior changed, and no path or machine-specific dependency entered the test.
- [ ] **Step 2: Independently run** `python -m pytest tests/test_preserved_physical_layout.py -q`, `python -m ruff check tests/test_preserved_physical_layout.py`, and `git diff --check` in the worker worktree. Expected: pass and no whitespace errors.
- [ ] **Step 3: Record the trial outcome.** Include elapsed time, local token usage if available, cloud usage from actual records if available, correction rounds, check results, and whether tool use and the edit completed. Do not claim cost savings without comparable actual usage.
- [ ] **Step 4: Integrate only after approval of the diff and checks.** Commit the single-file change on the pilot branch, then carry the reviewed commit to `feat/logical-layer-plotter`; otherwise leave the frontier branch unchanged and report the blocking result.
