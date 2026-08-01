# Development Plan: AI Software Engineering Assistant

This document outlines the step-by-step implementation plan for the AI Software Engineering Assistant, breaking down the build order (from `idea.md §8` and `engineering.md`) into detailed phases, subphases, and clear responsibilities between the AI Assistant (me) and the Developer (you).

## Phase 1: Foundation (State, Scaffold, and Logging)

**Objective**: Set up the physical repository structure, the core Pydantic state schemas with full validation, and the structured logging mechanism.

### Subphases:
1. **Repository Scaffolding**
   - **AI**: Create the directory structure in `agent_system/` (agents, tools, schemas, config, logging, persona).
   - **AI**: Create empty `__init__.py` files to establish the package.
   - **AI**: Write the initial `pyproject.toml` with `openai-agents>=0.18.3`, `pydantic>=2.0`, and `python-dotenv`.
   - **You**: Run `pip install -e .` to resolve and pin the exact dependencies in your environment.
   - **You**: Create the `.env` file from `.env.example` and add your API keys (Google AI Studio / Groq).

2. **SessionState & Validation (`schemas/state.py`)**
   - **AI**: Implement all Pydantic models from `engineering.md §6`.
   - **AI**: Replace the dead `requirements_spec_requires_issue` validator with the first real chain link (`requirements_spec` requires `triage_result`).
   - **AI**: Implement the rest of the `@model_validator` guards (e.g., `patch` requires `requirements_spec`, `test_result` requires `patch`).
   - **AI**: Write `tests/test_schemas.py` to verify validators.
   - **You**: Run `pytest tests/test_schemas.py` to confirm the schemas are bulletproof.

3. **Structured Logging (`logging/session_log.py`)**
   - **AI**: Implement a JSONL logger that formats tool calls and handoff events according to NFR-1.

4. **Target Repository Scaffolding (`demo_repo/`)**
   - **AI**: Build the `task_tracker` package with its seeded case-sensitivity bug (for #42) and priority filter feature gap (for #43), exactly matching `prd.md §11.1`.
   - **AI**: Write a passing baseline test suite (`pytest`) so the environment is ready for T-3 sandbox operations.

## Phase 2: CLI Entry & Orchestrator (Triage)

**Objective**: Get a minimal runnable script that loads an issue and performs Triage.

### Subphases:
1. **Config & API Keys (`config/models.py` & `config/settings.py`)**
   - **AI**: Implement the multi-provider config mapping `heavy` to Gemini and `lightweight` to Groq.
   
2. **Issue Payload Loading**
   - **AI**: Seed `issues/bug_42.json`, `feature_43.json`, and `partial_44.json` with the demo repo payloads.
   - **AI**: Build `__main__.py` to parse `--issue <path>`.

3. **Orchestrator Skeleton (`orchestrator.py`)**
   - **AI**: Implement the `Orchestrator` agent using `openai-agents`.
   - **AI**: Wire it to classify the issue and set `SessionState.triage_result`.
   - **You**: Run `python -m agent_system run --issue issues/bug_42.json` and verify the Triage output in the logs.

## Phase 3: Tool Implementations (The 5 Tools)

**Objective**: Build and test all 5 tools in isolation before any other agents use them.

### Subphases:
1. **T-2: Repo Search/Grep (`tools/repo_search.py`)**
   - **AI**: Implement the `grep_search` functionality.
2. **T-3: Pytest Runner & Sandbox (`tools/pytest_runner.py`)**
   - **AI**: Implement the sandbox lifecycle (copy `demo_repo/`, apply patch, run pytest).
   - **AI**: Ensure the sandbox survives through the session (per `engineering.md` decisions log, not I-2 which is just mutation isolation).
3. **T-4: Linter (`tools/linter.py`)**
   - **AI**: Implement the `ruff` subprocess call.
4. **T-1 & T-5: GitHub API (`tools/github_read.py`, `tools/github_write.py`)**
   - **AI**: Implement mock/JSON fallbacks for the demo, and live API paths gated by `GITHUB_LIVE_MODE`.
5. **Tool Unit Tests (`tests/tools/`)**
   - **AI**: Write unit tests for all tools.
   - **You**: Run `pytest tests/tools/` and resolve any local environment issues (e.g., ensuring `ruff` and `pytest` are in your PATH).

## Phase 4: Core Agent Wiring

**Objective**: Wire up the remaining 6 specialist agents to the `SessionState` and their respective tools.

### Subphases:
1. **Bug Investigation & Requirements Analysis**
   - **AI**: Implement these two agents. Bug Investigation gets T-2 (Grep).
2. **The Reflection Loop (Coding ⇄ Testing ⇄ Code Reviewer)**
   - **AI**: Implement `coding_assistant.py` (has T-2).
   - **AI**: Implement `testing_agent.py` (uses T-3 Pytest Sandbox).
   - **AI**: Implement `code_reviewer.py` (uses T-4 Linter).
   - **AI**: Implement the `iteration_count` loop logic (`< 3` for retry, `>= 3` for PARTIAL).
3. **Documentation Writer**
   - **AI**: Implement `documentation_writer.py` (uses T-2 to grep sandbox for docstrings).
4. **Agent Unit Tests**
   - **AI**: Write tests mocking the LLM responses to ensure handoffs trigger correctly.

## Phase 5: Human Gate & PR Creation

**Objective**: Close the loop with the human approval gate (Invariant I-1).

### Subphases:
1. **Gate CLI Interactivity**
   - **AI**: Implement the interactive `[A] Approve, [F] Feedback, [R] Reject` loop in `__main__.py` or `orchestrator.py`.
   - **AI**: Ensure PARTIAL state forces human intervention.
   - **AI**: Implement the single-automated-pass logic for `Request Changes` cycles.
2. **PR Dispatch & Cleanup**
   - **AI**: Connect `Approve` to T-5 (PR creation).
   - **AI**: Ensure `Reject` discards the sandbox and branches (Invariant I-3).
   - **You**: Run a full manual test of the CLI UI using a dummy issue and interact with the Gate.

## Phase 6: Persona & Polish (Optional but Planned)

**Objective**: Add the Rick Sanchez output decorator.

### Subphases:
1. **Persona Decorator (`persona/decorator.py`)**
   - **AI**: Implement the LLM call that rewrites the Orchestrator's final narrative output.
   - **AI**: Gate it behind `PERSONA_ENABLED`.
   - **You**: Toggle `PERSONA_ENABLED=true` in your `.env` and run a test to verify the output style.

## Phase 7: Integration, Benchmark, and KPIs

**Objective**: Run the system against the benchmark set and finalize NFR-4 and KPI targets.

### Subphases:
1. **Benchmark Seeding**
   - **AI/You**: Seed issues #45 through #55 in `issues/benchmark/` based on the coverage table in `engineering.md §10`.
2. **Integration Runs**
   - **You**: Run the system against all 10+ benchmark issues.
   - **You**: Record performance (latency) and convergence rates.
3. **Spec Finalization**
   - **AI**: Update `prd.md §8.2` (K-1, K-2, K-3) and `engineering.md §9` with the real measured numbers from your runs.
   - **AI**: Write invariant tests `tests/test_invariants.py` (T-INV-1, 2, 3) to formally verify safety.
   - **You**: Final run of `pytest` across the entire test suite.

---

## How We Work Together During the Build

1. **AI (Me)** writes the code, handles the Pydantic schemas, wires up the OpenAI Agents SDK, and sets up the tests.
2. **Developer (You)** executes the shell commands (`pip install`, `pytest`, `python -m agent_system ...`), manages the `.env` file (API keys), tests the CLI interactively, and provides feedback on integration runs.
3. We will work sequentially through these phases. I will not move to Phase N+1 until you have verified Phase N runs successfully on your local machine.
