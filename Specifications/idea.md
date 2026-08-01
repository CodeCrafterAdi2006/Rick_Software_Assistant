# idea.md — AI Software Engineering Assistant (Capstone Seed Doc)

> Purpose of this file: this is the single seed document that captures what I want to build and how I want it built. Every other spec (`prd.md`, `design.md`, `engineering.md`) should be generated **from** this file, one at a time, and each should stay consistent with it. If a later spec contradicts this file, either update this file deliberately (and log why in the decisions log inside `engineering.md`) or fix the later spec — don't let them silently drift.

**[Update — consolidated to 3 spec files]** Originally planned as 6 separate files (`prd.md`, `product.md`, `design.md`, `engineering.md`, `agents.md`, `decisions.md`). After the PRD audit pass, consolidated to 3, since the rubric grades content, not file count:

- `prd.md` absorbs `product.md` — business case + UX flow live in one doc, since there wasn't enough distinct content to justify splitting them.
- `design.md` absorbs `agents.md` — architecture and per-agent responsibility tables live together, since the agent table is the architecture at this project's size.
- `engineering.md` absorbs `decisions.md` as its final section — a running dated log of decisions/trade-offs, kept lightweight (one line per entry) rather than split into its own file. If any entry outgrows a few lines, that's the signal to split it out later — don't pre-split.

---

## 1. What this project is

An **AI Software Engineering Assistant** built on the OpenAI Agents SDK. It plugs into a GitHub repository and automates the loop a developer normally does by hand:

`issue opened → understand it → plan the fix/feature → write code → test it → review it → document it → open a PR for a human to approve`

This is capstone project option **#13** from the Summer School '26 assignment (Domain: Software Development). The full grading rubric (Problem Analysis, Multi-Agent Design, Implementation, Advanced Features, Deliverables) lives in the assignment brief — this idea.md is *my* framing of it, not a restatement of the rubric.

---

## 2. Why I'm building it this way (process philosophy)

- **Spec before code.** I write `prd.md`, `design.md`, `engineering.md` before touching the agent SDK. Each has a narrow job (see §5) so they don't turn into one giant messy doc.
- **One spec at a time, in order.** I don't want multiple half-finished docs. Finish one, review it, then move to the next.
- **Build fundamentally, not all at once.** I build the smallest working *skeleton* of the full pipeline first (agents that hand off to each other with dummy/mocked logic), prove the architecture works end-to-end, and only then go deep on any one agent or tool. This keeps the system understandable at every step instead of debugging six fully-built agents wired together for the first time.
- **Understanding over speed.** The point of this project (beyond the grade) is that I can explain every design decision in an interview. If I don't understand why an agent exists or why a handoff happens, I stop and fix that before adding more.
- **Decisions log as a living log.** Any time I change direction (e.g. "dropped RAG, going with plain repo grep instead"), it gets one dated entry — what changed, why, what I gave up — in the decisions log at the end of `engineering.md`.

---

## 3. Core user experience (high level — detailed flow goes in prd.md's UX section)

1. A GitHub issue is opened/labeled on a target repo (or pasted in manually for demo purposes, so the demo doesn't depend on live GitHub webhooks working perfectly).
2. The system classifies it: bug vs feature request.
3. It produces a structured, human-readable plan (acceptance criteria, files likely touched, risks) — the human can review/edit this before any code is written.
4. It writes a patch, runs tests against it, and iterates against its own reviewer agent up to a small retry limit.
5. **A human approval gate** sits before anything is opened as a real PR — the system never merges or pushes unattended.
6. On approval, it opens a PR with the patch, updated docs/changelog, and a summary of what the agents did and why.
7. For pure bug reports, a separate Bug Investigation path does root-cause analysis (searches repo/logs) and reports findings even if it can't fix the bug outright.

---

## 4. Agents (minimum 5 required — target set)

1. **Orchestrator / Triage** — reads the issue, classifies it, routes to the right specialist(s), owns the overall session/context.
2. **Requirements Analysis** — turns a raw issue into a structured spec (JSON: scope, acceptance criteria, out-of-scope notes).
3. **Coding Assistant** — implements a patch from the spec.
4. **Code Reviewer** — critiques the patch (correctness, style, security); can send it back to Coding Assistant (bounded retry loop).
5. **Testing Agent** — writes/runs tests against the patch, reports pass/fail.
6. **Documentation Writer** — updates README/docstrings/changelog to match the patch.
7. **Bug Investigation** — separate path for bug reports: root-causes using repo search before any fix is attempted.

(7 agents listed, rubric requires 5 minimum — Bug Investigation and Documentation Writer are the first candidates to cut or simplify if scope needs trimming.)

---

## 5. The specs I'm about to write, and what each one owns (3-file structure)

To avoid overlap/duplication between docs, each spec has a strict scope:

- **`prd.md`** — the "why" and "what the user experiences": business context, stakeholders, problem statement, objectives, success metrics (maps to rubric's "Problem Analysis"), plus the detailed step-by-step UX flow, inputs/outputs at each step, and what the human sees and approves at the gate.
- **`design.md`** — the "what the system looks like": agent architecture diagram, handoff flow, tool integration overview, data flow between agents, and one section per agent (single responsibility, inputs, outputs, tools it can call, handoff triggers in/out) — this is the file I'll keep open while writing agent code.
- **`engineering.md`** — the "how it's actually built": tech stack, exact SDK version pinned with date, model/provider configuration (see §10), repo structure, session/memory/state management, structured output schemas, error handling and logging approach, testing strategy for the system itself, and a running dated decisions log as its final section (one line per entry: what changed, why, what I gave up).

---

## 6. Tools/APIs I expect to need (≥5 required by rubric)

- GitHub API (read issues, open PRs, comment)
- Code execution/sandbox (run tests)
- Repo search/grep tool (for bug investigation + context gathering)
- Static analysis / linter tool (for Code Reviewer)
- Vector store / embeddings (only if I keep RAG as an advanced feature — decide in design.md)

Exact tool list gets finalized in `engineering.md`, not here.

---

## 7. Advanced features — candidates, not commitments

Pick 2–3 max, don't spread thin (per my own capstone plan): RAG over the codebase, reflection loop (Reviewer ⇄ Coding Assistant), structured logging/error handling for a clean demo. Long-term memory and multi-modal input are explicitly lower priority unless time allows.

---

## 8. Build order (fundamentals first)

1. Repo scaffold + agent skeletons wired with **handoffs only**, dummy instructions, no real tools — prove the orchestration shape works.
2. Add GitHub API + repo search as real tools.
3. Build the Coding Assistant ⇄ Testing Agent ⇄ Code Reviewer loop with structured outputs.
4. Add the human-approval gate + session persistence.
5. Add Documentation Writer + Bug Investigation paths.
6. Layer in chosen advanced features.
7. Diagram, docs, slides, demo video — last, once behavior is stable.

---

## 9. Open questions to resolve while writing the other specs

- Single target demo repo (my own small OSS-style repo) — needs to be picked before `prd.md`'s UX section can describe a concrete flow.
- RAG: full vector DB, or is repo grep + file search sufficient for the codebase sizes I'll demo against?

*(Resolved via PRD audit: demo issue input is local CLI/JSON payload, not live GitHub webhooks — see decisions log in `engineering.md`. Human-approval gate is a CLI prompt, no web UI needed.)*

---

## 10. SDK, model/provider strategy, and persona (decided after framework research)

- **Stay on the OpenAI Agents SDK** — don't switch frameworks. The assignment brief literally names "Openai-Agents SDK" in its title, so that's treated as a hard requirement, not a suggestion. LangChain/LangGraph/Google ADK are not adopted, even though they're reasonable frameworks in general.
- **The staleness worry was legitimate — checked and resolved.** The Agents SDK shipped a major update in April 2026 (model-native harness, native sandbox execution, configurable memory, and — critically — the SDK is now **provider-agnostic**, working with 100+ non-OpenAI models through an OpenAI-compatible interface). `engineering.md` must pin the exact SDK version and date used, so the project reads as built against current tooling rather than a stale tutorial.
- **Model/provider strategy** — fixes the "API key not working" problem without switching frameworks. OpenAI has no standing free API tier as of 2026 (credit card required), which is almost certainly why the key wasn't working — billing, not a bug. Instead of switching frameworks, point the Agents SDK's provider-agnostic client at free-tier models:
  - **Primary**: Google AI Studio, Gemini 2.5 Flash — genuinely free, no credit card, ~1,500 requests/day, 1M token context. Best default for most agents.
  - **Secondary/fallback**: Groq — free, very fast, good for lighter agents (e.g. Triage classification) that don't need heavy reasoning.
  - **Optional variety**: OpenRouter — free tier aggregates multiple open models behind one key, useful if different agents want different open models without juggling separate keys.
  - OpenAI itself stays supported as an optional path if a paid key is ever configured, defaulting to the free stack otherwise. This also becomes a legitimate "model-agnostic architecture" talking point in `design.md`.
- **Persona: Rick Sanchez (C-137)**, as a swappable skin — not baked into core agent logic. Fictional character, not a real person, so the creative choice itself is fine. Implementation constraint: the persona is a decorator/wrapper on top of the Orchestrator's final response, never embedded in the actual agents' reasoning instructions (Requirements Analysis, Coding Assistant, Reviewer, etc. stay professional and rubric-clean underneath). Toggleable in one line — off for the version shown to an internship recruiter/interviewer, on for personal demos. This itself is a decisions-log-worthy engineering choice: *"personality layer implemented as an output decorator, not agent instructions, to keep core reasoning demo-clean and the persona removable."*

---

*Next step: pick the demo repo (closes the one remaining open question in §9), then write `prd.md` from this file (now including the UX flow), review it, then move to `design.md`.*
