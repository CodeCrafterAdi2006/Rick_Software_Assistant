from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from pydantic import BaseModel, ConfigDict, Field, model_validator


# ─── Tool Error ───────────────────────────────────────────────────────────────

class ToolError(BaseModel):
    """Structured tool error returned on tool failures per engineering.md §7.1."""
    tool: str
    error_type: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


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
    __test__ = False
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
    model_config = ConfigDict(validate_assignment=True)

    # Session metadata
    session_id: Optional[str] = None

    # Set by Orchestrator
    issue: IssuePayload
    triage_result: Optional[TriageResult] = None
    # NOTE: classification is read from triage_result.classification — no bare field.

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
    def validate_handoff_chain(self) -> "SessionState":
        """Chain validators: prevent non-deterministic agent skipping (NFR-3)."""
        # Guard 1: Requirements spec requires triage result
        if self.requirements_spec is not None and self.triage_result is None:
            raise ValueError(
                "requirements_spec requires triage_result to be set first — "
                "Orchestrator must classify the issue before Requirements Analysis runs."
            )

        # Guard 1b: On BUG path, requirements_spec requires root_cause_report
        if (
            self.triage_result is not None
            and self.triage_result.classification == "BUG"
            and self.requirements_spec is not None
            and self.root_cause_report is None
        ):
            raise ValueError(
                "requirements_spec on BUG path requires root_cause_report to be set first — "
                "Bug Investigation must complete before Requirements Analysis runs."
            )

        # Guard 2: Patch requires requirements spec
        if self.patch is not None and self.requirements_spec is None:
            raise ValueError(
                "patch requires requirements_spec to be set first — "
                "Coding Assistant cannot generate a patch without a requirements spec."
            )

        # Guard 3: Test result requires patch
        if self.test_result is not None and self.patch is None:
            raise ValueError(
                "test_result requires patch to be set first — "
                "Testing Agent cannot run pytest without a patch to execute."
            )

        # Guard 4: Review result requires test result
        if self.review_result is not None and self.test_result is None:
            raise ValueError(
                "review_result requires test_result to be set first — "
                "Code Reviewer cannot evaluate a patch until test results are present."
            )

        # Guard 5: Doc updates requires review result (decision == APPROVED)
        if self.doc_updates is not None:
            if self.review_result is None:
                raise ValueError(
                    "doc_updates requires review_result to be set first — "
                    "Documentation Writer cannot run without code review."
                )
            if self.review_result.decision != "APPROVED":
                raise ValueError(
                    "doc_updates requires review_result.decision == 'APPROVED' — "
                    "Documentation Writer runs only after code review approval."
                )

        # Guard 6: Gate decision requires doc_updates OR status in ("PARTIAL", "ERROR")
        if self.gate_decision is not None:
            if self.status not in ("PARTIAL", "ERROR") and self.doc_updates is None:
                raise ValueError(
                    "gate_decision requires doc_updates to be complete unless status is 'PARTIAL' or 'ERROR'."
                )

        return self
