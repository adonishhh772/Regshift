import pytest

from app.services.workflow_trace import build_workflow_trace_summary


def test_build_workflow_trace_summary_includes_all_steps():
    summary = build_workflow_trace_summary(
        "test-session",
        session={
            "id": "test-session",
            "domain": "procurement",
            "contract_approved": 0,
        },
    )
    assert summary["session_id"] == "test-session"
    assert len(summary["steps"]) >= 10
    assert "langfuse" in summary
    assert "classify_change" in summary["all_steps"]
