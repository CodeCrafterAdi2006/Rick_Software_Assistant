from __future__ import annotations
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import gradio as gr
from dotenv import load_dotenv

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent_system.cli import load_issue_payload, resume_after_gate, run_to_gate_generator
from agent_system.config.settings import Settings
from agent_system.schemas.state import IssuePayload, SessionState

load_dotenv()

# Path to Rick image asset
RICK_IMAGE_PATH = PROJECT_ROOT / "assets" / "rick.png"

# Custom CSS for Professional Dark Palette
CUSTOM_CSS = """
body, .gradio-container {
    background-color: #0D1117 !important;
    color: #E6EDF3 !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
}

.rick-speech-box {
    background-color: #161B22;
    border: 2px solid #58C8F5;
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 12px;
    position: relative;
    box-shadow: 0 4px 14px rgba(88, 200, 245, 0.12);
}

.rick-speech-box::after {
    content: '';
    position: absolute;
    bottom: -10px;
    left: 40px;
    border-width: 10px 10px 0;
    border-style: solid;
    border-color: #58C8F5 transparent;
    display: block;
    width: 0;
}

.rick-dialogue {
    color: #58C8F5;
    font-size: 1.02rem;
    font-weight: 600;
    line-height: 1.45;
    margin: 0;
}

.header-banner {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 18px;
    background-color: #161B22;
    border: 1px solid #30363D;
    border-radius: 8px;
    margin-bottom: 16px;
}

.header-title {
    margin: 0;
    color: #E6EDF3;
    font-size: 1.4rem;
    font-weight: 700;
    letter-spacing: -0.02em;
}

.header-subtitle {
    color: #7D8590;
    font-size: 0.95rem;
    font-weight: 400;
    margin-left: 6px;
}

.gate-banner {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 18px;
    background: rgba(88, 200, 245, 0.08);
    border-left: 4px solid #58C8F5;
    border-radius: 6px;
    margin-bottom: 12px;
}

.gate-title {
    font-weight: 700;
    color: #58C8F5;
    font-size: 1.05rem;
    letter-spacing: 0.03em;
}

.gate-approve-btn {
    background-color: #238636 !important;
    color: #FFFFFF !important;
    font-weight: 600 !important;
    border-radius: 6px !important;
}

.gate-reject-btn {
    background-color: #DA3633 !important;
    color: #FFFFFF !important;
    font-weight: 600 !important;
    border-radius: 6px !important;
}

.gate-request-btn {
    background-color: #D29922 !important;
    color: #FFFFFF !important;
    font-weight: 600 !important;
    border-radius: 6px !important;
}

.run-pipeline-btn {
    background-color: #1F6FEB !important;
    color: #FFFFFF !important;
    font-weight: 600 !important;
    border-radius: 6px !important;
}
"""

# SVG Icons
FLASK_SVG = """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#58C8F5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2v7.527a2 2 0 0 1-.211.896L4.72 20.55a1 1 0 0 0 .9 1.45h12.76a1 1 0 0 0 .9-1.45l-5.069-10.127A2 2 0 0 1 14 9.527V2"/><path d="M8.5 2h7"/><path d="M7 16h10"/></svg>"""
SHIELD_SVG = """<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#58C8F5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>"""

# Speech Bubble Dialogue Dictionary
SPEECH_DIALOGUES: Dict[str, Dict[str, str]] = {
    "idle": {
        "plain": "Select an issue payload or enter a custom issue to begin pipeline execution.",
        "rick": "Listen Morty, paste your issue payload and let me fix whatever mess your developers made...",
    },
    "triage": {
        "plain": "Step 1/5: Triaging issue classification (BUG vs FEATURE)...",
        "rick": "Classifying your issue, genius. Try to keep up.",
    },
    "bug_investigation": {
        "plain": "Step 2/5: Investigating root cause hypothesis via code grep...",
        "rick": "Grep-ping through your garbage codebase. Science time.",
    },
    "requirements": {
        "plain": "Step 3/5: Generating structured requirements specification...",
        "rick": "Writing specs your developers were too lazy to write. You're welcome.",
    },
    "reflection": {
        "plain": "Step 4/5: Executing patch diff & running tests in isolated Pytest sandbox...",
        "rick": "Generating patch diff and running tests in my isolated dimension. Science.",
    },
    "doc_writer": {
        "plain": "Step 5/5: Generating changelog & updated docstrings...",
        "rick": "Writing changelog. Nobody reads these but I'm a professional.",
    },
    "human_gate": {
        "plain": "Pipeline complete. Awaiting human approval gate decision [A/F/R]...",
        "rick": "It's decision time, Morty. Approve, reject, or ask for changes. Don't overthink it.",
    },
    "approved": {
        "plain": "Gate Decision: APPROVED. Pull Request created successfully!",
        "rick": "PR opened. You're welcome. Try not to revert it.",
    },
    "rejected": {
        "plain": "Gate Decision: REJECTED. Sandbox discarded without PR creation.",
        "rick": "Smart move. Sandbox purged. Nothing happened.",
    },
    "error": {
        "plain": "Pipeline Error encountered during execution.",
        "rick": "Great. Your API key ran out of juice. Even I have limits, Morty.",
    },
}


def get_dialogue(state_key: str) -> str:
    """Returns speech bubble dialogue text based on state_key and PERSONA_ENABLED setting."""
    persona = Settings.is_persona_enabled()
    mode = "rick" if persona else "plain"
    dialogues = SPEECH_DIALOGUES.get(state_key, SPEECH_DIALOGUES["idle"])
    return dialogues.get(mode, dialogues["plain"])


def get_available_issue_files() -> List[str]:
    """List all available issue JSON files in issues/ and issues/benchmark/."""
    issue_files = []
    
    root_issues = PROJECT_ROOT / "issues"
    if root_issues.exists():
        for f in sorted(root_issues.glob("*.json")):
            issue_files.append(f.relative_to(PROJECT_ROOT).as_posix())

    bench_issues = PROJECT_ROOT / "issues" / "benchmark"
    if bench_issues.exists():
        for f in sorted(bench_issues.glob("*.json")):
            if f.name != "benchmark_results.json":
                issue_files.append(f.relative_to(PROJECT_ROOT).as_posix())

    return issue_files if issue_files else ["issues/bug_42.json"]


# Store current session state globally per user session
class AppSession:
    def __init__(self) -> None:
        self.state: Optional[SessionState] = None


session_store = AppSession()


def run_pipeline_ui(
    input_mode: str,
    selected_issue_file: str,
    custom_id: int,
    custom_title: str,
    custom_body: str,
    custom_author: str,
    custom_labels: str,
):
    """Gradio generator callback for live pipeline execution streaming."""
    if input_mode == "Benchmark Payload":
        issue_path = PROJECT_ROOT / selected_issue_file
        if not issue_path.exists():
            yield (
                get_dialogue("error"),
                "**[ERROR]**: Issue file not found.",
                "", "", "", "", "",
                gr.update(visible=False),
            )
            return
        issue_input = issue_path
    else:
        labels_list = [l.strip() for l in custom_labels.split(",") if l.strip()]
        issue_input = IssuePayload(
            id=int(custom_id or 99),
            title=custom_title or "Custom Bug",
            body=custom_body or "Bug description",
            author=custom_author or "anonymous",
            labels=labels_list if labels_list else ["bug"],
        )

    # Check GROQ_API_KEY
    if not os.getenv("GROQ_API_KEY"):
        yield (
            get_dialogue("error"),
            "**[ERROR]**: GROQ_API_KEY is missing. Please configure it in System Settings.",
            "", "", "", "", "",
            gr.update(visible=False),
        )
        return

    # Run pipeline generator
    try:
        gen = run_to_gate_generator(issue_input)
        last_state = None

        for state in gen:
            last_state = state
            session_store.state = state

            # Determine dialogue key
            if state.status == "ERROR":
                diag_key = "error"
            elif state.doc_updates is not None:
                diag_key = "human_gate"
            elif state.review_result is not None:
                diag_key = "doc_writer"
            elif state.test_result is not None:
                diag_key = "reflection"
            elif state.requirements_spec is not None:
                diag_key = "reflection"
            elif state.root_cause_report is not None:
                diag_key = "requirements"
            elif state.triage_result is not None:
                diag_key = "bug_investigation" if state.triage_result.classification == "BUG" else "requirements"
            else:
                diag_key = "triage"

            dialogue_text = get_dialogue(diag_key)

            # Format outputs
            status_text = f"**Status**: `{state.status}` | **Session ID**: `{state.session_id}` | **Iterations**: `{state.iteration_count}`"
            
            patch_diff = state.patch.diff if state.patch else "No patch generated yet."
            
            test_summary = "No tests executed yet."
            if state.test_result:
                test_summary = f"Status: {state.test_result.status}\nPassed: {state.test_result.passed}\nFailed: {state.test_result.failed}\n\nTracebacks:\n" + "\n".join(state.test_result.tracebacks)

            review_summary = "No code review yet."
            if state.review_result:
                review_summary = f"Decision: {state.review_result.decision}\nCritique: {state.review_result.critique}\nLints: {state.review_result.linter_output}"

            doc_summary = "No documentation updates yet."
            if state.doc_updates:
                doc_summary = f"Changelog Entry:\n{state.doc_updates.changelog_entry}\n\nDocstring Diffs:\n" + "\n".join(state.doc_updates.docstring_diffs)

            session_log = json.dumps(state.model_dump(mode="json"), indent=2)

            gate_visible = gr.update(visible=True) if state.status in ("IN_PROGRESS", "PARTIAL") and state.requirements_spec is not None else gr.update(visible=False)

            yield (
                dialogue_text,
                status_text,
                patch_diff,
                test_summary,
                review_summary,
                doc_summary,
                session_log,
                gate_visible,
            )

        if last_state and last_state.status != "ERROR":
            dialogue_text = get_dialogue("human_gate")
            session_store.state = last_state
            yield (
                dialogue_text,
                status_text,
                patch_diff,
                test_summary,
                review_summary,
                doc_summary,
                session_log,
                gr.update(visible=True),
            )

    except Exception as e:
        yield (
            get_dialogue("error"),
            f"**[ERROR]**: {e}",
            "", "", "", "", "",
            gr.update(visible=False),
        )


def handle_gate_action(decision: str, feedback: str):
    """Callback for Human Gate buttons [Approve / Request Changes / Reject]."""
    state = session_store.state
    if not state:
        return (
            get_dialogue("error"),
            "**[ERROR]**: No active session found.",
            "", "", "", "", "",
            gr.update(visible=False),
        )

    updated_state = resume_after_gate(state, decision=decision, feedback=feedback)
    session_store.state = updated_state

    if decision == "APPROVE":
        dialogue = get_dialogue("approved")
    elif decision == "REJECT":
        dialogue = get_dialogue("rejected")
    else:
        dialogue = get_dialogue("reflection")

    status_text = f"**Status**: `{updated_state.status}` | **Gate Decision**: `{updated_state.gate_decision}`"
    patch_diff = updated_state.patch.diff if updated_state.patch else "No patch."
    test_summary = f"Status: {updated_state.test_result.status}" if updated_state.test_result else "No tests."
    review_summary = f"Decision: {updated_state.review_result.decision}" if updated_state.review_result else "No review."
    doc_summary = f"Changelog: {updated_state.doc_updates.changelog_entry}" if updated_state.doc_updates else "No docs."
    session_log = json.dumps(updated_state.model_dump(mode="json"), indent=2)

    return (
        dialogue,
        status_text,
        patch_diff,
        test_summary,
        review_summary,
        doc_summary,
        session_log,
        gr.update(visible=False),
    )


def save_settings(groq_key: str, github_token: str, live_mode: bool, persona_enabled: bool):
    """Saves updated settings to environment and .env file."""
    if groq_key:
        os.environ["GROQ_API_KEY"] = groq_key.strip()
    if github_token:
        os.environ["GITHUB_TOKEN"] = github_token.strip()

    os.environ["GITHUB_LIVE_MODE"] = "true" if live_mode else "false"
    os.environ["PERSONA_ENABLED"] = "true" if persona_enabled else "false"

    groq_status = "[CONFIGURED]" if os.getenv("GROQ_API_KEY") else "[MISSING]"
    github_status = "[CONFIGURED]" if os.getenv("GITHUB_TOKEN") else "[OPTIONAL - MOCK MODE]"
    live_status = "ON (Real PR Creation)" if live_mode else "OFF (Mock PR Mode)"
    persona_status = "ON (Rick Dialogue Active)" if persona_enabled else "OFF (Plain Status Mode)"

    return f"**Settings Updated**\n\n- Groq API Key: `{groq_status}`\n- GitHub Token: `{github_status}`\n- Live GitHub Mode: `{live_status}`\n- Persona Mode: `{persona_status}`"


# Build Gradio Interface
with gr.Blocks(title="Rick Software Assistant") as demo:
    gr.HTML(f"""
    <div class="header-banner">
        {FLASK_SVG}
        <div>
            <h1 class="header-title">Rick Software Assistant <span class="header-subtitle">| Multi-Agent Autonomous Engineering Platform</span></h1>
        </div>
    </div>
    """)

    # Settings Modal Accordion
    with gr.Accordion("Settings & API Configuration", open=False):
        with gr.Row():
            groq_input = gr.Textbox(
                label="GROQ API Key",
                type="password",
                value=os.getenv("GROQ_API_KEY", ""),
                placeholder="gsk_...",
            )
            github_input = gr.Textbox(
                label="GitHub Personal Access Token (Optional)",
                type="password",
                value=os.getenv("GITHUB_TOKEN", ""),
                placeholder="ghp_...",
            )
        with gr.Row():
            live_mode_chk = gr.Checkbox(
                label="Enable Live GitHub Mode (Open Real PRs)",
                value=Settings.is_github_live_mode(),
            )
            persona_chk = gr.Checkbox(
                label="Enable Rick Sanchez Persona Dialogue",
                value=Settings.is_persona_enabled(),
            )
        save_btn = gr.Button("Save Configuration", variant="secondary")
        settings_output = gr.Markdown()

        save_btn.click(
            fn=save_settings,
            inputs=[groq_input, github_input, live_mode_chk, persona_chk],
            outputs=[settings_output],
        )

    # Main 3-Column Layout
    with gr.Row():
        # Left Column: Rick Avatar & Contextual Speech Bubble
        with gr.Column(scale=3):
            speech_box = gr.HTML(
                f'<div class="rick-speech-box"><p class="rick-dialogue">{get_dialogue("idle")}</p></div>'
            )
            if RICK_IMAGE_PATH.exists():
                gr.Image(
                    value=str(RICK_IMAGE_PATH),
                    show_label=False,
                    interactive=False,
                    container=False,
                )
            else:
                gr.Markdown("*(Rick Avatar Image)*")

        # Center Column: Issue Input & Progress Status
        with gr.Column(scale=5):
            input_mode_radio = gr.Radio(
                choices=["Benchmark Payload", "Custom Issue"],
                value="Benchmark Payload",
                label="Issue Input Selection Mode",
            )

            # Benchmark Mode Container
            with gr.Group() as bench_group:
                issue_dropdown = gr.Dropdown(
                    choices=get_available_issue_files(),
                    value=get_available_issue_files()[0] if get_available_issue_files() else "issues/bug_42.json",
                    label="Select Benchmark Issue JSON Payload",
                )

            # Custom Issue Mode Container
            with gr.Group(visible=False) as custom_group:
                custom_id_num = gr.Number(value=42, label="Issue ID (integer)")
                custom_title_txt = gr.Textbox(value="Core filter crash", label="Issue Title")
                custom_body_txt = gr.Textbox(value="Description of the defect or feature requirement...", lines=3, label="Issue Body")
                custom_author_txt = gr.Textbox(value="dev_user", label="Author")
                custom_labels_txt = gr.Textbox(value="bug", label="Labels (comma-separated)")

            def toggle_input_mode(mode):
                return (
                    gr.update(visible=mode == "Benchmark Payload"),
                    gr.update(visible=mode == "Custom Issue"),
                )

            input_mode_radio.change(
                fn=toggle_input_mode,
                inputs=[input_mode_radio],
                outputs=[bench_group, custom_group],
            )

            run_btn = gr.Button("Execute Multi-Agent Pipeline", elem_classes=["run-pipeline-btn"])
            status_markdown = gr.Markdown("**Status**: `IDLE` | Select an issue payload to begin execution.")

        # Right Column: Detailed Output Artifact Tabs
        with gr.Column(scale=4):
            with gr.Tabs():
                with gr.Tab("Patch Diff"):
                    patch_output = gr.Code(language=None, label="Generated Patch Diff")
                with gr.Tab("Test Execution"):
                    test_output = gr.Textbox(lines=8, label="Pytest Sandbox Output")
                with gr.Tab("Code Review & Lints"):
                    review_output = gr.Textbox(lines=8, label="Reviewer Critique & Lints")
                with gr.Tab("Documentation"):
                    doc_output = gr.Textbox(lines=8, label="Generated Doc Updates & Changelog")
                with gr.Tab("Session Telemetry"):
                    log_output = gr.Code(language="json", label="Structured Session Telemetry")

    # Bottom Human Approval Gate Row
    with gr.Column(visible=False) as gate_row:
        gr.HTML(f"""
        <div class="gate-banner">
            {SHIELD_SVG}
            <span class="gate-title">HUMAN APPROVAL GATE (Safety Invariant I-1)</span>
        </div>
        """)
        with gr.Row():
            approve_btn = gr.Button("Approve & Open Pull Request", elem_classes=["gate-approve-btn"])
            reject_btn = gr.Button("Reject Session (Purge Sandbox)", elem_classes=["gate-reject-btn"])
        with gr.Row():
            feedback_txt = gr.Textbox(placeholder="Enter feedback for Coding Assistant retry...", label="Request Changes Feedback")
            request_btn = gr.Button("Request Changes & Retry Pass", elem_classes=["gate-request-btn"])

    # Wire Pipeline Run Event
    run_btn.click(
        fn=run_pipeline_ui,
        inputs=[
            input_mode_radio,
            issue_dropdown,
            custom_id_num,
            custom_title_txt,
            custom_body_txt,
            custom_author_txt,
            custom_labels_txt,
        ],
        outputs=[
            speech_box,
            status_markdown,
            patch_output,
            test_output,
            review_output,
            doc_output,
            log_output,
            gate_row,
        ],
    )

    # Wire Gate Action Events
    approve_btn.click(
        fn=lambda: handle_gate_action("APPROVE", ""),
        outputs=[speech_box, status_markdown, patch_output, test_output, review_output, doc_output, log_output, gate_row],
    )

    reject_btn.click(
        fn=lambda: handle_gate_action("REJECT", ""),
        outputs=[speech_box, status_markdown, patch_output, test_output, review_output, doc_output, log_output, gate_row],
    )

    request_btn.click(
        fn=lambda fb: handle_gate_action("REQUEST_CHANGES", fb),
        inputs=[feedback_txt],
        outputs=[speech_box, status_markdown, patch_output, test_output, review_output, doc_output, log_output, gate_row],
    )


if __name__ == "__main__":
    demo.launch(server_port=7861, css=CUSTOM_CSS)
