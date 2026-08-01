# Product Requirements Document (PRD): AI Software Engineering Assistant

> **Document Status**: v6 — Final PRD  
> **Source Seed**: [idea.md](file:///c:/AI%20Native%20founder/IIT%20Jammu%20Assignments/Final_project_2/idea.md)  
> **Target Capstone**: Option #13 (Domain: Software Development, Summer School '26)  
> **Owner**: Development Team  
> **Changes from v5**: Expanded §11.4 PARTIAL gate mockup to match FR-8.1 completeness — added PLAN, FILES, LINTER, DIFF and AGENT LOG pager rows (consistent with READY screen). Footer Next Step updated from `design.md` (already complete) to `engineering.md`. Filled §11.4 mockup placeholders with concrete issue #44 content (consistent with §11.5). Version header corrected from v5 → v6.

---

## 1. Executive Summary

The **AI Software Engineering Assistant** is an autonomous, multi-agent developer system designed to streamline and automate routine software maintenance tasks within GitHub repositories. Operating on top of the OpenAI Agents SDK, the system ingests GitHub issues (bug reports or feature requests), conducts requirements analysis and bug root-causing, generates code patches, verifies changes against automated test suites, subjects code to an internal reflection review loop, updates relevant documentation, and presents a human developer with an actionable Pull Request (PR) for final approval.

By maintaining strict human-in-the-loop oversight before any code is pushed or merged, the system enhances developer productivity while eliminating the risk of rogue automated commits.

---

## 2. Problem Analysis & Background

### 2.1 The Problem
Software development teams and open-source maintainers spend a disproportionate amount of time on routine maintenance:
- **Triage & Context Switching**: Manually deciphering ambiguous bug reports and feature requests.
- **Repetitive Fixes**: Writing boilerplate patches, unit tests, and updated docstrings for simple bugs or small feature additions.
- **Review Overhead**: Spending senior engineering cycles on basic code review, linter checks, and style verification.
- **Documentation Drift**: Code modifications often lack matching documentation updates due to rush or oversight.

### 2.2 Domain Context (Capstone Option #13)
In modern software engineering, AI assistants must progress beyond single-turn code generation (e.g., inline autocompletion) to **multi-turn, agentic workflows** capable of tool usage, environment feedback (test runners/linters), reflection loops, and structured state handoffs.

---

## 3. Product Vision & Goals

### 3.1 Core Vision
To provide a reliable, transparent, and multi-agent AI co-pilot that acts as a junior developer—taking raw repository issues and turning them into thoroughly tested, reviewed, and documented PRs under human guidance.

### 3.2 Key Objectives (Goals)
1. **End-to-End Automation**: Automate the flow from issue ingestion to PR draft creation.
2. **Multi-Agent Specialization**: Employ specialized agents (Triage, Requirements, Bug Investigation, Coding, Testing, Review, Documentation) rather than a monolith LLM prompt.
3. **Safety First**: Enforce a mandatory, un-bypassable Human Approval Gate before any remote Git mutation or PR creation occurs.
4. **Reflection & Self-Correction**: Enable bounded reflection loops between Testing/Reviewer agents and the Coding Assistant to fix bugs iteratively before human intervention.
5. **Clear Auditability**: Maintain full visibility into agent reasoning, tool calls, and state transitions for ease of evaluation and debugging.

### 3.3 Non-Goals (Out of Scope for Initial Release)
- **Unattended Auto-Merging**: The system will **never** automatically merge PRs or push directly to protected main branches.
- **Large-Scale Architecture Redesigns**: The system targets localized bugs, component additions, and refactoring — not multi-repo, cross-service architectural rewrites.
- **Full Autonomous CI/CD Pipeline Management**: The system runs tests locally inside a sandbox environment rather than managing external cloud infrastructure pipelines.

---

## 4. Stakeholders & User Personas

### 4.1 Primary Persona (Demo Subject)

> **Junior / Feature Developer**  
> Resolves assigned GitHub issues, writes tests and docs. Needs assistance with root-cause analysis, faster bug resolution, and automated test generation.  
> **This is the persona that the demo video and the UX flow section of this prd.md will follow end-to-end.**

### 4.2 Secondary Personas

| Stakeholder / Persona | Role & Objectives | Key Needs from System |
| :--- | :--- | :--- |
| **Open Source Maintainer / Senior Developer** | Approves PRs, maintains repo quality, sets standards. | High-quality PR summaries, passing test suites, clean diffs, zero breaking changes. |
| **Capstone Evaluator / Technical Interviewer** | Evaluates software architecture, agent design, and implementation rigor. | Transparent agent handoffs, clean architecture, adherence to grading rubric, clear decision logs. |

---

## 5. Functional Requirements

### FR-1: Issue Ingestion & Triage
- **FR-1.1**: The system shall accept issue inputs via two modes:
  - **Primary (Demo default)**: Local CLI/JSON payload — a structured JSON file representing a GitHub issue. This is the default for the demo to avoid live webhook dependencies.
  - **Secondary**: GitHub API / Webhook integration for production-style integration.
- **FR-1.2**: The **Orchestrator/Triage Agent** shall classify incoming issues as either a `Bug Report` or a `Feature Request` and route to the appropriate pipeline.

### FR-2: Requirements & Scope Analysis
- **FR-2.1**: The **Requirements Analysis Agent** shall convert unstructured issue descriptions into a structured JSON specification including:
  - Scope Summary
  - Explicit Acceptance Criteria (testable, binary pass/fail)
  - Target Component / File Boundaries (candidate files and modules)
  - Out-of-Scope Constraints

### FR-3: Bug Root-Cause Investigation (Bug Path Only)
- **FR-3.1**: For `Bug Report` classifications, the **Bug Investigation Agent** shall use the shared **Repo Search/Grep Tool** to locate relevant source files, trace stack traces, and isolate potential root causes before coding begins.
- **FR-3.2**: The Bug Investigation Agent shall produce a structured root-cause report (file path, suspected lines, hypothesis) as input to the Coding Assistant.

### FR-4: Context Gathering & Code Patch Generation
- **FR-4.1 (Both Paths — Context Gathering)**: Before writing any patch, the **Coding Assistant Agent** shall use the shared **Repo Search/Grep Tool** to inspect relevant source files, understand the existing codebase structure, and identify the precise change locations. On the **Feature path**, this search starts from scratch using the acceptance criteria in FR-2. On the **Bug path**, FR-4.1's context gathering is scoped by and extends the FR-3.2 root-cause report rather than repeating it from scratch — the Coding Assistant uses the report's file paths and suspected lines as its starting point, then searches further only if needed.
- **FR-4.2 (Patch Generation)**: The **Coding Assistant Agent** shall produce a modular, focused code patch adhering to the structured requirements specification from FR-2.

### FR-5: Automated Test Execution
- **FR-5.1**: The **Testing Agent** shall invoke the local test runner (`pytest`) inside an isolated sandbox workspace directory.
- **FR-5.2**: If tests fail, the Testing Agent shall extract full error tracebacks and structured failure summaries and return them to the Coding Assistant for self-correction.

### FR-6: Automated Code Review, Linting & Reflection Loop
- **FR-6.1**: The **Code Reviewer Agent** shall analyze proposed code diffs for:
  - Correctness against acceptance criteria (FR-2)
  - Security risks (e.g., injection, unsafe eval)
  - Style compliance via the **Static Analysis / Linter Tool** (e.g., `ruff` or `pylint`)
- **FR-6.2**: The system shall enforce a **bounded reflection loop** (maximum 3 retry attempts) allowing the Code Reviewer and Testing Agent to request revised patches from the Coding Assistant.
- **FR-6.3 (Loop Exhaustion Behavior)**: If the maximum retry limit is reached and tests still fail or the reviewer still rejects the patch, the system shall **escalate to the Human Approval Gate** with a `PARTIAL` status — presenting the human with the last patch attempt, the full failure log, and an explicit note that automated convergence failed. The human may then Approve, Reject, or inject feedback to attempt one further manual iteration.

### FR-7: Documentation Maintenance
- **FR-7.1**: The **Documentation Writer Agent** shall detect code signature changes or new features introduced by the patch and update relevant docstrings, `README.md` sections, or changelog entries.

### FR-8: Human Approval Gate & PR Creation
- **FR-8.1**: Before opening a Pull Request, the system shall pause and present a comprehensive summary to the human reviewer via CLI, including: plan summary, test results (pass/fail), code diff, doc updates, agent action log, and **total iteration count for the current run** (coding loop retries + human-requested revisions combined).
- **FR-8.2**: The human shall have three options:
  - **Approve**: System proceeds to open a GitHub PR with structured metadata.
  - **Request Changes (with feedback)**: Human provides a free-text note. The system injects this as additional context and re-enters the pipeline from the Coding Assistant (not bounded by FR-6.2's loop — the human's continued engagement is the effective cap on this outer loop).
  - **Reject**: Human permanently abandons this run. The system discards the working branch, logs the rejection with reason in the session log, and exits cleanly. No PR is opened.
- **FR-8.3**: Upon explicit `Approve`, the system shall open a GitHub Pull Request with structured metadata summarizing agent actions, test results, and the reasoning chain.
- **FR-8.4 (Iteration Transparency)**: The system shall maintain a global iteration counter across the full run (FR-6.2 coding loop retries + human `Request Changes` cycles). This counter shall be displayed at each human gate presentation. There is **no hard system cap** on human-initiated iterations — the human is the cap. This is by design: the coding loop (FR-6.2) is bounded to prevent runaway autonomous loops; the human gate loop is intentionally left open because a human is present and accountable for each cycle.

### FR-9: Linter Tool Integration (Supporting FR-6.1)
- **FR-9.1**: The system shall invoke a static analysis tool (default: `ruff`; configurable to `pylint`) on each candidate patch before the Code Reviewer evaluates it.
- **FR-9.2**: Linter output (warnings, errors, line references) shall be passed to the Code Reviewer as structured context, not as raw subprocess output.

---

## 6. Non-Functional Requirements (NFRs)

- **NFR-1: Transparency & Logging**: Every agent handoff, tool invocation, and decision step must produce structured JSON log entries readable post-run.
- **NFR-2: Execution Safety**: Code execution for test suites must occur in an isolated local workspace copy or temp directory, preventing host environment contamination.
- **NFR-3: Determinism**: State transitions and human gate interventions must be strictly enforced via Pydantic-validated state schemas to prevent non-deterministic agent skipping.
- **NFR-4: Performance (Target to Validate)**: *Aspirational target, not yet baselined.* The full triage-to-human-gate pipeline for a standard, localized issue is expected to complete within a range to be determined in `engineering.md §[Performance & Latency]` after **build step 3** of the order defined in `idea.md §8` (the first full Coding Assistant ⇄ Testing Agent ⇄ Reviewer loop). This metric must be filled in with real numbers before final submission — the calibration note in K-1/K-2/K-3 applies here equally.

---

## 7. Rubric Alignment Matrix

This PRD directly aligns with the **Capstone Option #13 Grading Rubric**:

| Rubric Section | Requirement in Rubric | How this PRD Fulfills It |
| :--- | :--- | :--- |
| **Problem Analysis** | Clear domain formulation, problem scope, and baseline evaluation. | §2 (Problem Analysis) & §3 (Scope & Boundaries). |
| **Multi-Agent Design** | ≥5 specialized agents, defined communication protocols & handoffs. | §5 (7 specialized agents with explicit handoff-triggering FRs). |
| **Implementation** | Tool integrations (≥5), clean code, structured output schemas. | (1) **GitHub Issues API — read** (FR-1, issue ingestion); (2) **GitHub PR API — write** (FR-8.3, PR creation — different auth scope from read); (3) **Repo Search/Grep Tool** (FR-3, FR-4); (4) **Pytest test runner** (FR-5); (5) **Ruff/Pylint Linter** (FR-9) = 5 distinct runtime tool integrations. Pydantic schemas per NFR-3. |
| **Advanced Features** | Reflection loops, structured logging, human approval gate, bug investigation path. | FR-3 (Bug Path), FR-6 (Reflection Loop + Escalation), FR-8 (Human Gate with Reject/Feedback), NFR-1 (Structured Logging). |
| **Deliverables** | Complete documentation suite covering business case, UX, architecture, implementation, and decision log. | 3-file spec structure: `prd.md` (business case + UX flow), `design.md` (architecture + per-agent tables), `engineering.md` (implementation detail + decisions log). Sequential creation per process philosophy in `idea.md §2`. |

---

## 8. Safety Invariants & Quality KPIs

These are split into two distinct categories to avoid mixing architectural guarantees with measurable quality metrics.

### 8.1 Safety Invariants (Binary Pass/Fail — Architectural Guarantees)
These must hold on every run, without exception. Failure is a system defect, not a KPI miss.

| Invariant | Description |
| :--- | :--- |
| **I-1: Human Gate Enforcement** | A PR shall never be opened without an explicit human `Approve` action. This is enforced by architecture (gated state machine), not by convention. |
| **I-2: Sandbox Isolation** | Test execution shall never write to or mutate the original repository working directory. |
| **I-3: Reject Discards Branch** | A human `Reject` must result in no open PR and no persisted remote branch for that run. |

### 8.2 Quality KPIs (Aspirational Targets — Calibrated Against Demo Issue Set)
These are initial targets to be re-evaluated against a benchmark set of 10–15 demo issues once the system is running. They are not committed SLAs.

| KPI | Metric | Target | Benchmark Measured Value | Calibration Note |
| :--- | :--- | :--- | :--- | :--- |
| **K-1: Issue Resolution Rate** | % of benchmark issues where the system delivers a passing-tests patch | > 70% | **0.0%** (12/13 required human gate review; 1 rejected) | Calibrated across 13 benchmark issues (`issues/benchmark/`) |
| **K-2: Reflection Loop Convergence** | % of runs where Reviewer ⇄ Coding loop converges within 3 retries | > 65% | **0.0%** (Max reflection cap 3 enforced on complex synthetic benchmark set) | Calibrated across 13 benchmark issues (`issues/benchmark/`) |
| **K-3: Doc Coverage Rate** | % of PRs where the Documentation Writer produces at least one relevant doc update | > 85% | **100.0%** (for all APPROVED PR gate dispatches) | Verified on approved PR dispatches |

---

## 9. Open Questions & Explicit Assumptions

> [!IMPORTANT]
> These questions were raised in `idea.md §9`. Where a working assumption has been made in this PRD, it is noted explicitly so it can be revisited. OQ-2 (demo repo) must be resolved before the UX flow section of this prd.md can be written.

| # | Question | Status | Assumption / Decision Made in This PRD |
| :--- | :--- | :--- | :--- |
| **OQ-1** | Real GitHub webhook integration vs. scripted/mocked issue feed for the demo? | **Decided here** | Demo default is **local CLI/JSON payload** (FR-1.1). GitHub webhook is secondary. Decision rationale logged in `engineering.md` decisions log. |
| **OQ-2** | Which specific target demo repo will be used? | **Decided here** | **`task-tracker`** — a small, purpose-built Python task management library located at `demo_repo/` in this project. Contains realistic bugs, tests, and feature gaps designed to exercise all 7 agent paths. Repo structure: `src/task_tracker/` (core.py, utils.py), `tests/` (pytest), `pyproject.toml`. |
| **OQ-3** | How strict is the human approval gate UI? | **Decided here** | **CLI prompt** is sufficient (FR-8.2). No web UI required. Rationale: keeps demo setup zero-dependency. Decision rationale logged in `engineering.md` decisions log. |
| **OQ-4** | RAG with a vector DB, or plain repo grep + file search? | **Decided here** | **Repo grep + file search only** — RAG with a vector store is formally cut from scope. Rationale: codebase sizes used in the demo are small enough that file-search is sufficient, and adding a vector DB increases setup complexity without a proportional demo benefit. Logged in `engineering.md` decisions log. Note: with RAG cut, the Advanced Features story relies on (a) the Reviewer ⇄ Coding reflection loop (FR-6), (b) structured JSON logging (NFR-1), and (c) the human gate with partial-status escalation (FR-6.3, FR-8.4) — these together satisfy the rubric's advanced features spirit without RAG. |

---

## 10. SDK, Model/Provider Strategy & Persona

*Product-level framing only. Full model/provider configuration — exact SDK version, provider assignments per agent, API key configuration, rate-limit details — is owned by `engineering.md` per `idea.md §5`. See `idea.md §10` for the full rationale behind these decisions.*

- **SDK (hard requirement)**: The system is built on the **OpenAI Agents SDK** — mandated by the assignment brief. Alternative frameworks (LangChain, LangGraph, Google ADK) are not adopted.
  - **Product-relevant SDK property**: As of April 2026 the SDK is **provider-agnostic**, enabling the free-tier strategy below without locking to a single model vendor. This is a first-class architecture property — "model-agnostic" is a talking point in `design.md` and a demo strength.

- **Model/Provider Strategy**: The system uses a **free-tier-first, multi-provider strategy** for cost and reliability reasons. Most users of this capstone demo will not have a paid OpenAI API key, so the default stack uses genuinely free providers (no credit card). OpenAI remains supported as an optional path if a paid key is configured. Full provider assignments, fallback order, and configuration details live in `engineering.md`.

- **Persona — Rick Sanchez (C-137)**: A toggleable personality skin applied to the Orchestrator's final output only. Core agent reasoning (Requirements Analysis, Coding Assistant, Code Reviewer, etc.) is unaffected and remains professional and rubric-clean at all times. **Default: off** (for recruiter/interviewer/evaluator contexts). The implementation mechanism (output decorator vs. embedded instructions) is an `engineering.md` decision-log entry, not a product requirement.


---

## 11. UX Flow & Demo Script Skeleton

*This section fulfils prd.md's absorbed scope from product.md (per `idea.md §5`): detailed step-by-step UX flow, exact inputs/outputs at each agent step, and what the human sees and approves at the gate. All flows are written against the `task-tracker` demo repo (`demo_repo/`).*

---

### 11.1 Demo Repository Context

| Item | Detail |
| :--- | :--- |
| **Repo name** | `task-tracker` (located at `demo_repo/`) |
| **Language** | Python 3.9+ |
| **Structure** | `src/task_tracker/core.py`, `src/task_tracker/utils.py`, `tests/test_core.py`, `tests/test_utils.py` |
| **Test runner** | `pytest` (6 tests, all passing at baseline) |
| **Known seeded bug** | `TaskManager.list_tasks()` in `core.py` — when called with a lowercase status string (e.g. `"todo"`), it returns an empty list instead of matching tasks, because `TaskStatus` is a `str` enum and case-sensitive comparison silently fails. |
| **Seeded feature gap** | `list_tasks()` has no `priority` filter parameter, making it impossible to retrieve only high-priority tasks in one call. |
| **Benchmark issue set** | §8.2 commits to calibrating K-1/K-2/K-3 against 10–15 demo issues. The two issues above cover the video demo only. The full benchmark set (8–13 additional JSON payloads covering edge cases: empty issue body, conflicting criteria, multi-file bugs, etc.) is a **non-video deliverable** to be seeded in `issues/` before final KPI calibration. This is tracked as a task in `engineering.md`. |

---

### 11.2 Demo Scenario A — Bug Report Path

**The issue (JSON payload, loaded via CLI):**
```json
{
  "id": 42,
  "title": "list_tasks returns empty when filtering by lowercase status",
  "body": "When I call manager.list_tasks('todo') I get an empty list even though I have TODO tasks. Filtering only works if I use uppercase 'TODO'. This is inconsistent with the docs which show lowercase usage.",
  "labels": ["bug"],
  "author": "jsmith"
}
```

#### Step-by-step agent flow

**Step 1 — Orchestrator/Triage Agent**
- *Input*: Raw JSON issue payload above.
- *Action*: Reads title + body + label. Classifies as `Bug Report`. Logs: `{"type": "BUG", "confidence": 0.97}`.
- *Output*: Routes to Bug Investigation path. Passes raw issue text as session context.
- *Human sees*: `[✓] Triage complete — classified as BUG. Routing to Bug Investigation.`

**Step 2 — Requirements Analysis Agent**
- *Input*: Raw issue text from Orchestrator.
- *Action*: Produces a structured JSON spec.
- *Output*:
```json
{
  "scope": "Fix case-insensitive status filtering in TaskManager.list_tasks()",
  "acceptance_criteria": [
    "list_tasks('todo') returns the same results as list_tasks('TODO')",
    "list_tasks('in_progress') matches IN_PROGRESS tasks",
    "Existing passing tests continue to pass"
  ],
  "target_files": ["src/task_tracker/core.py"],
  "out_of_scope": ["Changing TaskStatus enum values", "Modifying test filenames"]
}
```
- *Human sees*: Nothing yet (internal step).

**Step 3 — Bug Investigation Agent**
- *Input*: Structured spec, raw issue, repo path.
- *Action*: Uses Repo Search/Grep Tool. Greps for `list_tasks`, `status`, `TaskStatus` in `core.py`. Locates line 67: `return [t for t in self._tasks.values() if t.status == status]`. Identifies root cause: direct equality comparison, no case normalization.
- *Output*:
```json
{
  "file": "src/task_tracker/core.py",
  "line": 67,
  "hypothesis": "t.status is a TaskStatus str-enum. Comparing to a raw lowercase string fails because 'todo' != 'TODO'. Fix: normalize input to uppercase before comparison, or accept TaskStatus enum directly and document the type contract."
}
```
- *Human sees*: `[✓] Bug Investigation complete. Root cause isolated: core.py:67.`

**Step 4 — Coding Assistant Agent**
- *Input*: Root-cause report + structured spec. Reads `core.py` in full.
- *Action*: Generates a targeted patch normalizing the status filter input.
- *Output patch*:
```diff
- def list_tasks(self, status: Optional[str] = None) -> List[Task]:
+ def list_tasks(self, status: Optional[str] = None) -> List[Task]:
      if status is None:
          return list(self._tasks.values())
-     return [t for t in self._tasks.values() if t.status == status]
+     normalized = status.upper() if isinstance(status, str) else status
+     return [t for t in self._tasks.values() if t.status == normalized]
```

**Step 5 — Testing Agent**
- *Input*: Patch applied to sandbox copy of `demo_repo/`.
- *Action*: Runs `pytest` in sandboxed workspace.
- *Output*: `6 passed, 0 failed.`
- *Human sees*: Nothing yet (internal loop).

**Step 6 — Code Reviewer Agent**
- *Input*: Patch diff + linter output (ruff clean) + test results.
- *Action*: Checks correctness (case normalization matches acceptance criteria), security (no eval, no injection surface), and style (ruff passes). 
- *Output*: `APPROVED` on first attempt. Iteration count: 1 of 3.

**Step 7 — Documentation Writer Agent**
- *Input*: Final approved patch.
- *Action*: Detects signature change on `list_tasks` (parameter type contract updated). Updates the docstring.
- *Output*:
```diff
- """List tasks, optionally filtered by status string."""
+ """List tasks, optionally filtered by status.
+
+ Args:
+     status: Optional status string or TaskStatus enum. Case-insensitive.
+              Pass None to return all tasks.
+ """
```

**Step 8 — Human Approval Gate (FR-8.1)**

The human sees the following CLI **summary screen** (diff and action log are available via pager — press `[D]` to expand diff, `[L]` to expand agent action log):

```
┌──────────────────────────────────────────────────┐
│  AI Software Engineering Assistant — Gate Review    │
├──────────────────────────────────────────────────┤
│ Issue #42 : list_tasks returns empty on lowercase   │
│ Type      : BUG                                      │
│ Status    : READY (all tests pass, reviewer approved) │
│ Iterations: 1 coding loop / 0 human revisions        │
├──────────────────────────────────────────────────┤
│ PLAN      : Normalize status input to uppercase      │
│ FILES     : src/task_tracker/core.py (+2 lines)      │
│ TESTS     : 6 passed, 0 failed                       │
│ DOCS      : list_tasks() docstring updated           │
│ LINTER    : ruff — 0 warnings                        │
│ DIFF      : [D] Press D to expand in pager           │
│ AGENT LOG : [L] Press L to expand action log         │
└──────────────────────────────────────────────────┘

Options: [A] Approve and open PR  [F] Request changes  [R] Reject
> 
```

*The summary screen satisfies FR-8.1's full requirement: plan, test results, files changed, doc updates, linter result, iteration count — all visible on one screen. The diff (`[D]`) and agent action log (`[L]`) are complete but long; presenting them via a pager is standard CLI practice and avoids wall-of-text that obscures the approve/reject decision.*

**Step 9 — PR Creation (on Approve)**
- System opens a GitHub PR titled: `fix(core): normalize status filter input in list_tasks [AI-assisted]`
- PR body includes: agent action log, test results, doc diff, and reasoning chain from Bug Investigation.

---

### 11.3 Demo Scenario B — Feature Request Path

**The issue (JSON payload):**
```json
{
  "id": 43,
  "title": "Add priority filter to list_tasks()",
  "body": "I want to be able to call manager.list_tasks(min_priority=3) and get only tasks with priority 3 or above. Right now I have to filter manually after calling list_tasks(). Should support combining with the status filter.",
  "labels": ["enhancement"],
  "author": "adev"
}
```

#### Step-by-step agent flow (abbreviated — differences from Bug path only)

| Step | Agent | Key Difference vs Bug Path |
| :--- | :--- | :--- |
| 1 | Orchestrator | Classifies as `Feature Request`. Skips Bug Investigation. Routes to Requirements Analysis directly. |
| 2 | Requirements Analysis | Produces spec with `min_priority: int` parameter and acceptance criteria for combined `status + priority` filtering. |
| 3 | *Bug Investigation skipped* | Feature path — no root-cause report. Coding Assistant starts context-gathering from scratch using the FR-2 spec. |
| 4 | Coding Assistant | Greps `core.py` to understand `list_tasks` signature. Adds `min_priority: Optional[int] = None` parameter and a chained filter. |
| 5 | Testing Agent | Runs baseline pytest (6 pass). Adds 2 new tests for `min_priority` filtering (both pass). Total: 8 passed. |
| 6 | Code Reviewer | Approves patch. Notes: new parameter is backward-compatible (default None). No security issues. |
| 7 | Doc Writer | Updates `list_tasks` docstring to document `min_priority` parameter. Updates `README.md` Quick Start example. |
| 8 | Human Gate | Presents summary showing `READY`, 8 tests passed, 2 files changed (core.py + README.md). |
| 9 | PR | Opens PR titled: `feat(core): add min_priority filter to list_tasks [AI-assisted]` |

---

### 11.4 PARTIAL Status Scenario (Reflection Loop Exhaustion — FR-6.3)

If the Coding Assistant fails to produce a passing patch after 3 retry attempts (e.g. the feature is more complex than expected or the fix introduces a regression), the human sees:

```
┌──────────────────────────────────────────────────┐
│  AI Software Engineering Assistant — Gate Review    │
├──────────────────────────────────────────────────┤
│ Issue #44 : list_tasks must return [] AND raise      │
│             ValueError for the same input           │
│ Type      : BUG                                      │
│ Status    : PARTIAL — max retries reached (3/3)       │
│ Iterations: 3 coding loop / 0 human revisions        │
├──────────────────────────────────────────────────┤
│ NOTE      : Automated convergence failed. The patch  │
│             below is the last attempt. Human review  │
│             required before any further action.      │
├──────────────────────────────────────────────────┤
│ PLAN      : Satisfy contradictory acceptance         │
│             criteria (empty list + ValueError)       │
│ FILES     : src/task_tracker/core.py                 │
│ TESTS     : 2 failed (see failure log below)         │
│ LINTER    : ruff — 0 warnings                        │
│ DIFF      : [D] Press D to expand in pager           │
│ AGENT LOG : [L] Press L to expand action log         │
└──────────────────────────────────────────────────┘

Options: [A] Approve anyway  [F] Give feedback & retry  [R] Reject
> 
```

*The PARTIAL screen follows the same structure and pager pattern as the READY screen — full plan/files/tests/linter/diff/log are all present. The only differences are the `PARTIAL` status banner, the convergence-failure NOTE, and the option wording (`Approve anyway` vs `Approve and open PR`). FR-8.1 compliance is maintained: if the human chooses `[A]`, a PR can still be opened from this screen, so all required information must be visible or one keypress away.*

This ensures the human is always the decision-maker when the automated loop cannot converge (I-1 invariant preserved).

---

### 11.5 Demo Run Script (Skeleton)

The demo will be run in the following sequence for the video/presentation:

```
1. Show demo_repo/ structure (src/, tests/, pyproject.toml) — 15 sec
2. Feed issue #42 (bug) JSON via CLI: python -m agent_system run --issue issues/bug_42.json
3. Narrate each agent step as it logs to stdout (triage → investigate → code → test → review → doc)
4. Show human gate CLI summary screen; press [D] to show diff pager, then [A] to approve
5. Show PR opened on GitHub (or simulated GitHub output if offline)
6. Repeat steps 2–5 for issue #43 (feature request) — explicitly narrate the skipped Bug Investigation step
7. PARTIAL scenario — do NOT rely on organic LLM failure:
   - Seed issue #44 before the recording: a deliberately pathological request with contradictory
     acceptance criteria (e.g. "function must return both an empty list AND raise ValueError
     for the same input") proven to exhaust the 3-retry loop in test runs.
   - Test issue #44 at least twice before recording to confirm it reliably triggers PARTIAL.
   - If pre-testing is inconclusive, cut this from the live run and instead narrate
     the PARTIAL behavior over the static §11.4 mockup screenshot (safer default).
```

**Total expected demo runtime**: ~5–8 minutes with narration.

---

*Next Step: `engineering.md` — tech stack, SDK version pin, Pydantic schemas, session management, error handling, logging format, repo structure, and the decisions log. (`design.md` is complete and has passed audit.)*
