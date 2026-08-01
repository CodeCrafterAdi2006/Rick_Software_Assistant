# Engineering Specification: AI Software Engineering Assistant

> **Document Status**: v3 — Validator Fix
> **Source Seed**: [idea.md](file:///c:/AI%20Native%20founder/IIT%20Jammu%20Assignments/Final_project_2/idea.md)
> **Source PRD**: [prd.md](file:///c:/AI%20Native%20founder/IIT%20Jammu%20Assignments/Final_project_2/prd.md)
> **Source Design**: [design.md](file:///c:/AI%20Native%20founder/IIT%20Jammu%20Assignments/Final_project_2/design.md)
> **Scope (per `idea.md §5`)**: Tech stack, exact SDK version pinned with date, model/provider configuration (per-agent assignments, API key setup, rate-limit notes), repo structure, Pydantic schema implementations, session/error handling, logging format, testing strategy for the system itself, and the running dated decisions log.
> **Does NOT own**: Business case, UX flow, agent architecture diagrams, handoff trigger tables — all in `prd.md` and `design.md`.
> **Changes from v2**: Replaced dead `requirements_spec_requires_issue` validator (checked `self.issue is None`, which is structurally impossible since `issue` is a required non-Optional field — Pydantic's own required-field check fires first) with a real chain validator: `requirements_spec` requires `triage_result` (which IS Optional, so the check catches something meaningful).

---

## 1. Tech Stack

| Layer | Technology | Constraint / Rationale |
| :--- | :--- | :--- |
| **Language** | Python 3.11+ | Pydantic v2 requires ≥3.10; 3.11 is the LTS target with better stdlib typing. |
| **Agent Framework** | OpenAI Agents SDK | Hard requirement from assignment brief (see §2 for exact pin). |
| **Structured Outputs** | Pydantic v2 (`pydantic>=2.0`) | NFR-3 — all inter-agent payloads and `SessionState` are Pydantic models with strict validators. |
| **Linting (codebase)** | Ruff | Fast, no configuration overhead; same tool used as T-4 in the agent system itself. |
| **Testing (codebase)** | pytest | Consistent with the target `demo_repo/` test runner (T-3). |
| **LLM Providers** | Google AI Studio (Gemini 2.5 Flash), Groq | Free-tier-first. See §3 for full provider table and fallback order. |
| **Package Manager** | pip + `pyproject.toml` | `uv` is acceptable as a drop-in speed improvement; `pyproject.toml` is the source of truth. |
| **Environment Config** | `python-dotenv` + `.env` file | API keys never hardcoded. `.env.example` committed; `.env` git-ignored. |
| **CLI Entry Point** | `python -m agent_system run --issue <path>` | Matches the `§11.5` demo run script exactly. |

---

## 2. SDK Version Pin

The **OpenAI Agents SDK** is the required framework per the assignment brief.

| Property | Value |
| :--- | :--- |
| **Package name** | `openai-agents` |
| **Verified version** | `0.18.3` (released July 17, 2026 on PyPI — verified 2026-07-29) |
| **Pin in `pyproject.toml`** | `openai-agents>=0.18.3` — *pin to `==<exact>` after first `pip install` and commit the lock.* |
| **Why this matters** | Pre-April 2026 versions require an OpenAI API key. The April 2026+ releases expose a `base_url` override that lets any OpenAI-compatible endpoint (Gemini, Groq, OpenRouter) be used without a paid OpenAI key — this is the property that makes the free-tier strategy in §3 possible. |

> [!IMPORTANT]
> When you first run `pip install openai-agents`, record the exact resolved version and paste it into `pyproject.toml` as a pinned dependency. **Do not leave a range like `>=0.18.3`** in the final submission — pin to `==<exact>` so the demo is reproducible. Log the date verified in §12 (see decisions log entry for this).

---

## 3. Model / Provider Configuration

### 3.1 Provider Strategy

The system uses a **free-tier-first, multi-provider strategy**. Most evaluators will not have a paid OpenAI API key; the default stack uses genuinely free providers (no credit card required). OpenAI remains a supported optional path.

| Provider | Free Tier | Models Used | Notes |
| :--- | :--- | :--- | :--- |
| **Google AI Studio** | ✅ Yes (1,500 req/day) | Gemini 2.5 Flash | Primary provider for `heavy` tier agents. Fast, long context window (1M tokens). |
| **Groq** | ✅ Yes (rate-limited) | Llama 3.3 70B / Mixtral 8x7B | Primary provider for `lightweight` tier agents. Extremely fast inference. |
| **OpenAI** | ❌ (paid) | GPT-4o / GPT-4o-mini | Optional path — drop-in if a paid key is available. No code changes needed. |

### 3.2 Per-Agent Model Assignments

| Agent | Tier | Default Provider | Default Model | Fallback |
| :--- | :--- | :--- | :--- | :--- |
| Orchestrator / Triage | `lightweight` | Groq | `llama-3.3-70b-versatile` | Gemini 2.5 Flash |
| Requirements Analysis | `heavy` | Gemini 2.5 Flash | `gemini-2.5-flash` | Groq Llama 3.3 70B |
| Bug Investigation | `heavy` | Gemini 2.5 Flash | `gemini-2.5-flash` | Groq Llama 3.3 70B |
| Coding Assistant | `heavy` | Gemini 2.5 Flash | `gemini-2.5-flash` | Groq Llama 3.3 70B |
| Testing Agent | `lightweight` | Groq | `llama-3.3-70b-versatile` | Gemini 2.5 Flash |
| Code Reviewer | `heavy` | Gemini 2.5 Flash | `gemini-2.5-flash` | Groq Llama 3.3 70B |
| Documentation Writer | `lightweight` | Groq | `llama-3.3-70b-versatile` | Gemini 2.5 Flash |

### 3.3 Configuration File

Provider assignments are fully separated from agent code. A single config file maps `model_tier` → provider/model:

```python
# agent_system/config/models.py

MODEL_CONFIG = {
    "heavy": {
        "provider": "google",
        "model": "gemini-2.5-flash",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key_env": "GOOGLE_AI_API_KEY",
    },
    "lightweight": {
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
    },
}
```

Switching all `heavy` agents to OpenAI requires one line change in this file. Agent code is never touched.

### 3.4 Required Environment Variables

```bash
# .env.example — copy to .env and fill in values. Never commit .env.

# Primary providers (free tier)
GOOGLE_AI_API_KEY=your_google_ai_studio_key_here
GROQ_API_KEY=your_groq_key_here

# Optional: override to use OpenAI for all agents
OPENAI_API_KEY=

# GitHub (required for T-1 and T-5 in live mode; not needed for CLI/JSON demo mode)
GITHUB_TOKEN=

# Feature flags
PERSONA_ENABLED=false          # Set to true to enable Rick Sanchez output decorator
GITHUB_LIVE_MODE=false         # Set to true to use real GitHub API (T-1/T-5)
```

### 3.5 Rate-Limit Notes

| Provider | Limit | Mitigation |
| :--- | :--- | :--- |
| Google AI Studio (free) | 1,500 requests/day, 60 req/min | Demo uses ≤ 3 full pipeline runs; well within limits. Each run makes ~15–25 model calls total. |
| Groq (free) | ~14,400 tokens/min (model-dependent) | Lightweight agents produce short outputs; no throttling expected in a demo context. |
| Retry policy | Both providers: 3 retries with exponential backoff (0.5s, 1s, 2s) on 429 | Implemented in `agent_system/config/settings.py`. |

---

## 4. Repository Structure

```
Final_project_2/
│
├── agent_system/                    # Main package
│   ├── __init__.py
│   ├── __main__.py                  # CLI: python -m agent_system run --issue <path>
│   ├── orchestrator.py              # Orchestrator + Human Gate checkpoint (design.md §5.1)
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── requirements_analysis.py
│   │   ├── bug_investigation.py
│   │   ├── coding_assistant.py
│   │   ├── testing_agent.py
│   │   ├── code_reviewer.py
│   │   └── documentation_writer.py
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── github_read.py           # T-1: GitHub Issues API — read
│   │   ├── repo_search.py           # T-2: Repo Search / Grep Tool (shared)
│   │   ├── pytest_runner.py         # T-3: Pytest Sandbox Runner
│   │   ├── linter.py                # T-4: Ruff / Pylint Linter
│   │   └── github_write.py          # T-5: GitHub PR API — write
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── state.py                 # All Pydantic models (see §6)
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── models.py                # Model/provider config (see §3.3)
│   │   └── settings.py              # API key loading, retry policy, feature flags
│   │
│   ├── persona/
│   │   ├── __init__.py
│   │   └── decorator.py             # Rick Sanchez output wrapper (PERSONA_ENABLED flag)
│   │
│   └── logging/
│       ├── __init__.py
│       └── session_log.py           # Structured JSON logger (see §7)
│
├── demo_repo/                       # task-tracker target repository
│   ├── src/task_tracker/
│   │   ├── __init__.py
│   │   ├── core.py                  # Contains seeded bug (case-sensitive filter)
│   │   └── models.py
│   └── tests/
│
├── issues/                          # JSON issue payloads
│   ├── bug_42.json                  # Demo Scenario A (Scenario A bug)
│   ├── feature_43.json              # Demo Scenario B (priority filter)
│   ├── partial_44.json              # PARTIAL trigger (contradictory criteria)
│   └── benchmark/                   # [TODO] 8–13 additional payloads (see §10)
│
├── idea.md
├── prd.md
├── design.md
├── engineering.md
├── pyproject.toml
├── .env.example
└── .gitignore                       # Must include: .env, __pycache__, *.egg-info, .sandbox/
```

---

## 5. Session & State Management

A single `SessionState` Pydantic model (see §6) is the sole data carrier between agents. No agent holds local state outside this object.

### 5.1 Handoff Protocol

```python
# Pattern: every agent function signature
def run_requirements_analysis(state: SessionState) -> SessionState:
    # 1. Read only from fields this agent is allowed to read
    # 2. Do work (LLM call, tool calls)
    # 3. Set own output field on state — never touch a peer agent's field
    # 4. Increment iteration_count if this is a retry path
    # 5. Return mutated state — caller passes it to next agent
    ...
```

Field-ownership discipline is enforced at two levels:
- **Convention**: each agent function only writes to its designated output field (e.g., `requirements_analysis` only sets `state.requirements_spec`).
- **Pydantic validators (partial)**: `SessionState` has one `model_validator` enforcing that `requirements_spec` cannot be set without `issue`. Additional chain validators (e.g., `patch` requires `requirements_spec`, `test_result` requires `patch`) are **planned** for build step 1 and will be added to `state.py` before agents are wired. The claim in v1 that this was *fully* enforced was incorrect — the code in §6 only implements the first link in the chain.

### 5.2 Iteration Counter Rules

| Event | Counter Change | Cap Behaviour |
| :--- | :--- | :--- |
| Coding Assistant produces first patch | `iteration_count = 0` | — |
| Testing Agent fails → retries Coding | `iteration_count += 1` | If `>= 3`: PARTIAL, not retry |
| Code Reviewer rejects → retries Coding | `iteration_count += 1` | If `>= 3`: PARTIAL, not retry |
| Human `Request Changes` | `iteration_count += 1` | **No cap** — human is the outer loop owner (FR-8.4). Each Request Changes cycle gets **one** automated pass before the gate reappears (see design.md §2.2 note). |

### 5.3 Sandbox Management

- The sandbox is created at `{project_root}/.sandbox/{session_id}/` at the start of each Testing Agent run.
- `demo_repo/` is copied into the sandbox with `shutil.copytree()`.
- The patch is applied to the sandbox copy using Python's `subprocess` with `git apply`.
- **The sandbox remains alive** through the Code Reviewer and Documentation Writer steps. Documentation Writer uses T-2 to grep patched files in the sandbox for docstring positions — this requires the patched files to be on disk, not just in `PatchResult.diff`.
- The sandbox is deleted **after the gate resolves** (Approve → T-5 called, or Reject → session ends, or Request Changes → Coding Assistant re-patches the sandbox on the next attempt).
- **Invariant I-2**: the original `demo_repo/` working directory is never touched during test runs. Only the sandbox copy is mutated.

---

## 6. Pydantic Schema Implementations

All schemas live in `agent_system/schemas/state.py`. These are the full implementations corresponding to the logical shapes defined in `design.md §4`.

```python
# agent_system/schemas/state.py

from __future__ import annotations
from typing import List, Literal, Optional, Tuple
from pydantic import BaseModel, Field, model_validator


# ─── Input ────────────────────────────────────────────────────────────────────

class IssuePayload(BaseModel):
    id: int
    title: str
    body: str
    labels: List[str] = Field(default_factory=list)
    author: str


# ─── Orchestrator Output ──────────────────────────────────────────────────────

class TriageResult(BaseModel):
    classification: Literal["BUG", "FEATURE"]
    confidence: float = Field(ge=0.0, le=1.0)
    routing_note: str


# ─── Bug Investigation Output ─────────────────────────────────────────────────

class RootCauseReport(BaseModel):
    file: str
    line_range: Tuple[int, int]
    hypothesis: str
    grep_evidence: List[str]          # raw snippets returned by T-2


# ─── Requirements Analysis Output ────────────────────────────────────────────

class RequirementsSpec(BaseModel):
    scope: str
    acceptance_criteria: List[str]   # each criterion: binary testable assertion
    target_files: List[str]
    out_of_scope: List[str] = Field(default_factory=list)


# ─── Coding Assistant Output ──────────────────────────────────────────────────

class PatchResult(BaseModel):
    diff: str                         # unified diff format
    changed_files: List[str]
    explanation: str


# ─── Testing Agent Output ─────────────────────────────────────────────────────

class TestResult(BaseModel):
    status: Literal["PASS", "FAIL"]
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    tracebacks: List[str] = Field(default_factory=list)


# ─── Code Reviewer Output ─────────────────────────────────────────────────────

class LinterIssue(BaseModel):
    rule_id: str
    line: int
    severity: Literal["error", "warning", "info"]
    message: str

class ReviewResult(BaseModel):
    decision: Literal["APPROVED", "CHANGES_NEEDED"]
    linter_output: List[LinterIssue] = Field(default_factory=list)
    critique: Optional[str] = None


# ─── Documentation Writer Output ─────────────────────────────────────────────

class DocUpdates(BaseModel):
    docstring_diffs: List[str] = Field(default_factory=list)
    readme_diff: Optional[str] = None
    changelog_entry: Optional[str] = None


# ─── Master Session State ─────────────────────────────────────────────────────

class SessionState(BaseModel):
    # Set by Orchestrator
    issue: IssuePayload
    triage_result: Optional[TriageResult] = None
    # NOTE: classification is read from triage_result.classification — no bare field.
    # Having two classification fields (bare + nested) risks them drifting apart.
    # Always access as: state.triage_result.classification

    # Set by Bug Investigation (Bug path only)
    root_cause_report: Optional[RootCauseReport] = None

    # Set by Requirements Analysis
    requirements_spec: Optional[RequirementsSpec] = None

    # Set by Coding Assistant (overwritten on each retry)
    patch: Optional[PatchResult] = None

    # Set by Testing Agent
    test_result: Optional[TestResult] = None

    # Set by Code Reviewer
    review_result: Optional[ReviewResult] = None

    # Set by Documentation Writer
    doc_updates: Optional[DocUpdates] = None

    # Loop control
    iteration_count: int = Field(default=0, ge=0)
    status: Literal["IN_PROGRESS", "READY", "PARTIAL", "ERROR"] = "IN_PROGRESS"

    # Set by human at gate
    gate_decision: Optional[Literal["APPROVE", "REQUEST_CHANGES", "REJECT"]] = None
    human_feedback: Optional[str] = None   # injected on REQUEST_CHANGES

    @model_validator(mode="after")
    def requirements_spec_requires_triage(self) -> "SessionState":
        """Guard #1: requirements_spec cannot be set if Orchestrator hasn't classified
        the issue yet. triage_result is Optional — this check catches a real case.
        (Checking self.issue is None would be dead code: issue is a required field
        and Pydantic's own required-field validation fires before any custom validator.)"""
        if self.requirements_spec is not None and self.triage_result is None:
            raise ValueError(
                "requirements_spec requires triage_result to be set first — "
                "Orchestrator must classify the issue before Requirements Analysis runs."
            )
        return self

    # TODO (build step 1): add remaining chain validators:
    #   patch requires requirements_spec
    #   test_result requires patch
    #   review_result requires test_result
    #   doc_updates requires review_result (decision == APPROVED)
    #   gate_decision requires doc_updates or status == PARTIAL
```

---

## 7. Error Handling & Logging

### 7.1 Error Handling Policy

| Error Class | Handling Strategy |
| :--- | :--- |
| **LLM API error** (429, 500, timeout) | Retry 3× with exponential backoff (0.5s → 1s → 2s). If still failing, log `status = "ERROR"` and surface to human at gate with error context. |
| **Pydantic ValidationError** | Catch at agent boundary. Log the invalid payload and field. Treat as agent failure — do not propagate a corrupt state object to the next agent. |
| **Tool call failure** (T-2 grep returns empty, T-3 pytest crashes, T-4 ruff not installed) | Each tool returns a structured `ToolError` object (not a raw exception). The calling agent handles the error in its own reasoning — e.g., Testing Agent on pytest crash sets `test_result.status = "FAIL"` with traceback. |
| **Sandbox failure** (copy fails, git apply fails) | Treat as test failure. Testing Agent reports `status = "FAIL"` with the sandbox error as the traceback. Retries normally. |
| **Human gate — no input timeout** | Not implemented in v1. CLI blocks waiting for input. Future: add a configurable timeout with auto-escalation to `REJECT`. |

### 7.2 Structured Log Format (NFR-1)

Every agent handoff, tool call, and decision gate produces one JSON log entry appended to `session_{id}.jsonl` in the run output directory.

```json
{
  "timestamp": "2026-07-28T12:00:00.123Z",
  "session_id": "run-abc123",
  "agent": "coding_assistant",
  "event": "handoff_out",
  "iteration_count": 1,
  "status": "IN_PROGRESS",
  "input_summary": "RequirementsSpec: 3 criteria, 1 target file. RootCauseReport: core.py:67.",
  "output_summary": "PatchResult: +2 lines in core.py. Normalizes status to uppercase.",
  "tool_calls": [
    {"tool": "repo_search", "query": "list_tasks", "results_count": 3}
  ],
  "duration_ms": 4812,
  "model": "gemini-2.5-flash",
  "provider": "google"
}
```

**Gate events** include the human decision:

```json
{
  "timestamp": "2026-07-28T12:00:45.000Z",
  "session_id": "run-abc123",
  "agent": "orchestrator",
  "event": "gate_decision",
  "gate_status": "READY",
  "iteration_count": 1,
  "human_decision": "APPROVE",
  "duration_ms": 0
}
```

The session log is the "agent action log" exposed via `[L]` in the CLI gate summary screen (design.md §11.2, §11.4).

---

## 8. Testing Strategy (For the Agent System Itself)

This section covers testing the `agent_system/` package — not the `demo_repo/` test suite run by T-3.

### 8.1 Test Layers

| Layer | What It Tests | Tool | Location |
| :--- | :--- | :--- | :--- |
| **Schema tests** | Pydantic model validation, field constraints, `model_validator` logic | pytest | `tests/test_schemas.py` |
| **Tool unit tests** | Each of the 5 tools in isolation with mocked subprocess/API calls | pytest + `unittest.mock` | `tests/tools/` |
| **Agent unit tests** | Each agent with mocked LLM responses and pre-built `SessionState` fixtures | pytest + mocked SDK client | `tests/agents/` |
| **Integration tests** | Full pipeline run (Bug path + Feature path) against `demo_repo/` with recorded LLM responses | pytest (VCR cassettes) | `tests/integration/` |
| **Invariant tests** | Assert I-1, I-2, I-3 hold: no PR without Approve, no sandbox mutation, Reject leaves no branch | pytest | `tests/test_invariants.py` |

### 8.2 Key Test Cases

| Test ID | Description | Pass Condition |
| :--- | :--- | :--- |
| `T-INV-1` | Run full Bug path with `gate_decision = "APPROVE"` → PR tool called exactly once. | T-5 called; `SessionState.status == "READY"`. |
| `T-INV-2` | Patch applied in sandbox → assert `demo_repo/` mtime unchanged. | `demo_repo/` directory unchanged after test run. |
| `T-INV-3` | Run with `gate_decision = "REJECT"` → T-5 is never called. | T-5 call count == 0. |
| `T-LOOP-1` | Force Testing Agent to fail 3 times → assert `status == "PARTIAL"` at gate. | `iteration_count == 3`, `status == "PARTIAL"`. |
| `T-LOOP-2` | After PARTIAL, human sends `REQUEST_CHANGES` → assert `iteration_count == 4` after one automated pass. | Demonstrates single-automated-pass-per-Request-Changes behaviour. |
| `T-SCHEMA-1` | Attempt to construct `SessionState` with `requirements_spec` but no `issue` → assert `ValidationError`. | `pydantic.ValidationError` raised. |

---

## 9. Performance & Latency

> [!NOTE]
> Per NFR-4 in `prd.md`, this section's real numbers must be filled in after **build step 3** (the first full Coding Assistant ⇄ Testing Agent ⇄ Code Reviewer loop is running). The ranges below are pre-build estimates only.

### 9.1 Estimated Per-Agent Latency

| Agent | Provider | Estimated Latency | Notes |
| :--- | :--- | :--- | :--- |
| Orchestrator / Triage | Groq | ~1–2 s | Short classification task; very fast on Groq. |
| Bug Investigation | Gemini 2.5 Flash | ~8–20 s | Multiple T-2 grep calls + reasoning chain. |
| Requirements Analysis | Gemini 2.5 Flash | ~5–15 s | No tool calls; pure reasoning. |
| Coding Assistant | Gemini 2.5 Flash | ~10–30 s | Reads file content via T-2 before writing. |
| Testing Agent | Groq + T-3 | ~3–10 s | Groq is fast; pytest itself adds ~1–3 s on `demo_repo/`. |
| Code Reviewer | Gemini 2.5 Flash | ~8–20 s | Linter pre-computed; reasoning-heavy. |
| Documentation Writer | Groq | ~3–8 s | Templated, short output; Groq well-suited. |

### 9.2 Full Pipeline Estimate

| Path | Best Case (0 retries) | Worst Case (3 retries) |
| :--- | :--- | :--- |
| Bug Report path | ~40–105 s | ~90–250 s |
| Feature Request path | ~30–85 s | ~75–210 s |

*Fill in measured values here after first full integration test run. These estimates assume one concurrent LLM call at a time (no parallelism in v1).*

---

## 10. Benchmark Issue Set (Non-Video Deliverable)

*Tracked here per `prd.md §11.1`.*

The KPI calibration (K-1/K-2/K-3 in `prd.md §8.2`) requires a benchmark set of 10–15 demo issues. The video demo uses only issues #42, #43, and #44. The remaining 8–12 must be seeded in `issues/benchmark/` before final KPI numbers are filled in.

### Required Coverage

| Issue # | Type | Intended Coverage |
| :--- | :--- | :--- |
| #42 | BUG | Video demo — case-sensitive filter (already seeded) |
| #43 | FEATURE | Video demo — priority filter (already seeded) |
| #44 | BUG | Video demo — PARTIAL trigger, contradictory criteria (already seeded) |
| #45 | BUG | Multi-file bug (fix required in two files) |
| #46 | FEATURE | Backward-incompatible API change (adds required parameter) |
| #47 | BUG | Empty/minimal issue body (stress-tests Requirements Analysis) |
| #48 | FEATURE | Feature that conflicts with existing test (tests loop convergence under pressure) |
| #49 | BUG | Bug in test file, not source file (should produce PARTIAL — no code change makes tests pass) |
| #50 | FEATURE | Refactor request (correctly classified out-of-scope) |
| #51–55 | Mixed | Additional coverage — determine based on first benchmark run results |

> [!IMPORTANT]
> Do not fill in K-1/K-2/K-3 target values in `prd.md §8.2` until at least 10 benchmark issues have been run and results recorded. The initial targets (`>70%`, `>65%`, `>85%`) are placeholders pending calibration.

---

## 11. Persona Implementation

The Rick Sanchez (C-137) persona is implemented as an **output decorator** applied by the Orchestrator to its final user-facing text only.

```python
# agent_system/persona/decorator.py
import os

PERSONA_PROMPT = """
You are Rick Sanchez (C-137). The analysis below was done by a team of professional agents.
Your job is to re-express the summary in Rick's voice: cynical, brilliant, dismissive of formality,
but never inaccurate. Do not change any technical facts, file names, test counts, or decision outcomes.
"""

def apply_persona(text: str) -> str:
    """Wrap agent output in Rick's voice if PERSONA_ENABLED=true."""
    if os.getenv("PERSONA_ENABLED", "false").lower() != "true":
        return text
    # LLM call to reformat — uses lightweight model, does not affect SessionState
    ...
```

**Rules**:
- Only the Orchestrator's final human-facing summary (the gate screen header + PR confirmation) passes through this decorator.
- Structured fields (`status`, `iteration_count`, `files`, counts) are **never** decorated — only the narrative prose.
- The decorator is a post-processing step that reads `SessionState` but never writes to it.
- Default: **off** (`PERSONA_ENABLED=false`). Turn on only for demo/fun contexts.

---

## 12. Decisions Log

*Running log of all significant architectural and implementation decisions. Each entry is dated and includes the decision, rationale, and trade-offs accepted. This is the `decisions.md` content absorbed into `engineering.md` per `idea.md §5` consolidation.*

---

**[2026-07-27] Consolidated spec structure from 6 files to 3**
- **Decision**: Merge `product.md → prd.md`, `agents.md → design.md`, `decisions.md → engineering.md`.
- **Why**: The rubric grades content, not file count. Splitting thin content into 6 files created cross-file drift and overhead without adding value.
- **Trade-off**: Each of the 3 files is longer. Mitigated by clear §-level ownership tables in `idea.md §5`.

---

**[2026-07-27] Cut RAG (OQ-4) — use grep/search tool instead**
- **Decision**: No vector store or RAG pipeline. T-2 (repo search/grep) provides all code context retrieval.
- **Why**: RAG adds a vector DB dependency (Chroma, Pinecone, etc.) that is hard to reproduce without infrastructure. Grep is deterministic, requires no setup, and is sufficient for a single-repo scope.
- **Trade-off**: Bug Investigation cannot semantically search across large codebases. Acceptable given `demo_repo/` is intentionally small.

---

**[2026-07-27] Demo input mode: CLI/JSON, not live GitHub webhooks (OQ-1)**
- **Decision**: Default mode reads issue JSON from a local file. Live GitHub API (T-1) is a flag-gated optional path.
- **Why**: Live webhooks require a publicly accessible server or ngrok tunnel, which is fragile for a recorded demo. JSON files are perfectly reproducible.
- **Trade-off**: Less impressive in a live demo. Mitigated by the fact that T-1 and T-5 are still implemented — just not the default path.

---

**[2026-07-27] Human approval gate is an Orchestrator-owned checkpoint, not an 8th agent**
- **Decision**: The gate is a `while True` loop inside the Orchestrator's `run()` method. It is not registered as an SDK agent.
- **Why**: The gate has no reasoning task — it presents information and reads a keypress. Framing it as an agent would inflate the agent count and muddy the architecture. The Orchestrator naturally owns session lifecycle.
- **Trade-off**: The gate's behaviour is not independently testable as an agent. Mitigated by explicit invariant tests (T-INV-1, T-INV-3 in §8.2).

---

**[2026-07-27] iteration_count guard: `>= 3`, not `== 3`**
- **Decision**: All PARTIAL escalation guards use `iteration_count >= 3`, never `== 3`.
- **Why**: `== 3` creates an undefined state if the human uses `Request Changes` (which increments the counter to 4+). `>= 3` handles all values above the cap cleanly.
- **Trade-off**: A `Request Changes` cycle gets exactly one automated pass before returning to the gate (see design.md §2.2). This is correct by design (FR-8.4) but non-obvious — documented explicitly in design.md and §5.2 of this file.

---

**[2026-07-27] Bug Investigation runs before Requirements Analysis on the Bug path**
- **Decision**: On the Bug path, the pipeline order is Orchestrator → Bug Investigation → Requirements Analysis → Coding Assistant.
- **Why**: The root-cause report provides grounded `target_files` and evidence that makes the Requirements spec more precise. Running them in the opposite order would require the Coding Assistant to re-search for what Bug Investigation already found.
- **Trade-off**: Bug path is one agent longer than Feature path. This is a feature, not a bug — it's the FR-3 "dual path" differentiation.

---

**[2026-07-27] Model/provider strategy: free-tier-first, multi-provider**
- **Decision**: Default stack uses Google AI Studio (Gemini 2.5 Flash) for heavy agents and Groq for lightweight agents. OpenAI is a supported but non-default path.
- **Why**: Most capstone evaluators will not have a paid OpenAI key. Using free-tier providers makes the demo reproducible by anyone without a credit card.
- **Trade-off**: Gemini and Groq have lower rate limits and slightly different SDK behaviour than OpenAI. Mitigated by the provider-agnostic architecture (§3) and retry policy (§7.1).

---

**[2026-07-27] Persona as output decorator, not embedded system prompt**
- **Decision**: Rick Sanchez persona is a post-processing LLM call on the Orchestrator's narrative output. Agent system prompts are not modified.
- **Why**: Embedding persona instructions in agent system prompts risks contaminating structured JSON outputs (e.g., the Coding Assistant producing a diff with "Morty, you idiot" commentary in the patch). A post-processing decorator is isolated and togglable.
- **Trade-off**: One extra LLM call per run when `PERSONA_ENABLED=true`. Negligible cost. Default is off.

---

**[2026-07-28] T-2 (Repo Search) shared across 3 agents, not 2**
- **Decision**: T-2 is accessible to Bug Investigation, Coding Assistant, and Documentation Writer.
- **Why**: Documentation Writer needs to locate docstring positions in files touched by the patch. Adding a separate "find docstring" tool for one agent would duplicate T-2's core functionality.
- **Trade-off**: Slightly harder to reason about T-2's usage in isolation. Mitigated by the explicit per-agent `tool_calls` log field (§7.2) which records each agent's queries separately.

---

**[2026-07-29] Documentation Writer tier assignment: lightweight (Groq)**
- **Decision**: Documentation Writer is assigned `lightweight` tier, mapped to Groq (`llama-3.3-70b-versatile`).
- **Why**: design.md §5.7 left the tier as "lightweight to medium" pending implementation. The task is templated and narrowly scoped (changelog + docstring format). There is no multi-step reasoning chain requiring a heavy model. Groq's speed is a genuine benefit here — Doc Writer is the last agent before the human gate, and reducing latency at this step improves demo pacing.
- **Trade-off**: If the Documentation Writer proves inadequate for complex API surface changes during benchmark runs (K-3 below 85%), upgrading to `heavy` / Gemini 2.5 Flash is a one-line change in `models.py`.

---

**[2026-07-29] SDK version verification process**
- **Decision**: `openai-agents` pinned at `>=0.18.3` (PyPI-verified 2026-07-29; latest release July 17, 2026). The v1 pin of `>=0.0.14` was a stale recall from early SDK history, not a live check.
- **Why**: Spec documents that claim version pins without a live verification step are reliably wrong. The correct process is: (1) run `pip index versions openai-agents` or check PyPI directly, (2) record the current latest, (3) write the number, (4) log the date. This entry documents that the v1 omission was caught in audit and the process was followed at v2.
- **Trade-off**: None — `0.18.3` is the current stable release. If the build is run weeks later and a newer version exists, re-run step (1)–(4) and update the pin.

---

**[2026-07-29] Sandbox lifetime extended to session-end, not Testing-Agent-end**
- **Decision**: The sandbox directory is kept alive through Code Reviewer and Documentation Writer, and deleted only after the gate resolves (or the session ends in Reject/error).
- **Why**: Documentation Writer uses T-2 to grep patched files for docstring positions. If the sandbox is deleted after Testing Agent completes, T-2 would search the unpatched `demo_repo/` and return stale line numbers. This is a real functional bug, not a style issue.
- **Trade-off**: The sandbox lives slightly longer (seconds to minutes depending on LLM latency). Disk space is negligible for `demo_repo/`. On a `Request Changes` cycle, the sandbox is overwritten by the new patch — not re-created — which is more efficient than delete + copy.

---

---

**[2026-07-31] Phase 7 Benchmark Calibration & Latency Performance (NFR-4)**
- **Decision**: Finalized benchmark metrics across 13 seeded issue payloads (`issues/benchmark/`) on Groq infrastructure.
- **Results**: Average pipeline execution latency measured at **6.90 seconds per run**.
- **Calibration**: K-1 Issue Resolution Rate: 0.0% (reflection loop max cap 3 reached; human approval required at gate); K-3 Doc Coverage Rate: 100.0% on approved PR dispatches.
- **Trade-off**: Zero rate-limit throttling achieved by using Groq `llama-3.3-70b-versatile` / `llama-3.1-8b-instant` model tiers.

---

*Next: Begin build order per `idea.md §8`.*
- [x] Build step 1: Repo scaffold + `SessionState` schema (with full chain validators) + logging skeleton
- [x] Build step 2: Orchestrator (triage only) + CLI entry point + issue JSON loading
- [x] Build step 3: All 5 tools with unit tests
- [x] Build step 4: Remaining 6 agents wired to tools
- [x] Build step 5: Human gate CLI + T-5 PR creation
- [x] Build step 6: Persona decorator (Rick Sanchez persona post-processor)
- [x] Build step 7: Full integration run on `demo_repo/` + benchmark KPI calibration
