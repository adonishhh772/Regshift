from contextlib import contextmanager
from typing import Any, Generator

from app.config import settings

_client = None
_langfuse_available: bool | None = None

TRACE_NAME_REGSHIFT = "regshift-change-workflow"

WORKFLOW_STEP_INTAKE = "intake"
WORKFLOW_STEP_POLICY_GRAPH_LOAD = "policy_graph_load"
WORKFLOW_STEP_CLASSIFY = "classify_change"
WORKFLOW_STEP_POLICY_INGEST = "policy_ingest"
WORKFLOW_STEP_CONTRACT_COMPILE = "contract_compile"
WORKFLOW_STEP_HUMAN_APPROVAL = "human_approval_gate"
WORKFLOW_STEP_INDEX_SCAN = "index_scan"
WORKFLOW_STEP_IMPACT_ANALYSIS = "impact_analysis"
WORKFLOW_STEP_GRAPH_PERSIST = "graph_persist"
WORKFLOW_STEP_RISK_SCORING = "risk_scoring"
WORKFLOW_STEP_TEST_GENERATION = "test_generation"
WORKFLOW_STEP_SIMULATION = "simulation"
WORKFLOW_STEP_GOVERNANCE = "governance_gate"
WORKFLOW_STEP_GOVERNANCE_EVALUATE = "governance_evaluate"
WORKFLOW_STEP_PACK_GENERATION = "pack_generation"

ALL_WORKFLOW_STEPS: list[str] = [
    WORKFLOW_STEP_INTAKE,
    WORKFLOW_STEP_POLICY_GRAPH_LOAD,
    WORKFLOW_STEP_CLASSIFY,
    WORKFLOW_STEP_POLICY_INGEST,
    WORKFLOW_STEP_CONTRACT_COMPILE,
    WORKFLOW_STEP_HUMAN_APPROVAL,
    WORKFLOW_STEP_INDEX_SCAN,
    WORKFLOW_STEP_IMPACT_ANALYSIS,
    WORKFLOW_STEP_GRAPH_PERSIST,
    WORKFLOW_STEP_RISK_SCORING,
    WORKFLOW_STEP_TEST_GENERATION,
    WORKFLOW_STEP_SIMULATION,
    WORKFLOW_STEP_GOVERNANCE,
    WORKFLOW_STEP_GOVERNANCE_EVALUATE,
    WORKFLOW_STEP_PACK_GENERATION,
]


def _get_client():
    global _client, _langfuse_available
    if not settings.langfuse_enabled:
        _langfuse_available = False
        return None
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        _langfuse_available = False
        return None
    if _langfuse_available is False:
        return None
    try:
        if _client is None:
            from langfuse import Langfuse

            _client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
            )
            _langfuse_available = True
        return _client
    except Exception:
        _langfuse_available = False
        _client = None
        return None


def langfuse_status() -> dict[str, Any]:
    client = _get_client()
    if client is None:
        return {
            "available": False,
            "enabled": settings.langfuse_enabled,
            "host": settings.langfuse_host,
            "ui_url": settings.langfuse_ui_url,
        }
    return {
        "available": True,
        "enabled": True,
        "host": settings.langfuse_host,
        "ui_url": settings.langfuse_ui_url,
    }


def flush_traces() -> None:
    client = _get_client()
    if client is not None:
        client.flush()


def build_session_trace_url(session_id: str) -> str | None:
    if not settings.langfuse_ui_url:
        return None
    base_url = settings.langfuse_ui_url.rstrip("/")
    return f"{base_url}/project/regshift-project/traces?search={session_id}"


@contextmanager
def trace_regshift_step(
    step_name: str,
    session_id: str,
    *,
    domain: str | None = None,
    input_data: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Generator[dict[str, Any], None, None]:
    output_holder: dict[str, Any] = {"data": {}}
    client = _get_client()
    span_metadata = {
        "session_id": session_id,
        "domain": domain,
        "workflow_step": step_name,
        **(metadata or {}),
    }

    if client is None:
        yield output_holder
        return

    from langfuse import propagate_attributes

    tags = ["regshift", domain or "unknown", step_name]
    with propagate_attributes(
        session_id=session_id,
        trace_name=TRACE_NAME_REGSHIFT,
        tags=tags,
        metadata={"domain": domain or "unknown", "step": step_name},
    ):
        with client.start_as_current_span(
            name=step_name,
            input=input_data or {},
            metadata=span_metadata,
        ) as span:
            try:
                yield output_holder
                span.update(
                    output=output_holder.get("data", {}),
                    metadata={**span_metadata, "status": output_holder.get("status", "completed")},
                )
            except Exception as error:
                span.update(
                    output={"error": str(error)},
                    metadata={**span_metadata, "status": "error"},
                )
                raise


@contextmanager
def trace_nested_step(
    step_name: str,
    *,
    input_data: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Generator[dict[str, Any], None, None]:
    output_holder: dict[str, Any] = {"data": {}}
    client = _get_client()
    if client is None:
        yield output_holder
        return

    with client.start_as_current_span(
        name=step_name,
        input=input_data or {},
        metadata={"workflow_step": step_name, **(metadata or {})},
    ) as span:
        try:
            yield output_holder
            span.update(output=output_holder.get("data", {}))
        except Exception as error:
            span.update(output={"error": str(error)})
            raise


trace_workflow_step = trace_regshift_step


def trace_policy_extraction(
    session_id: str,
    policy_id: str,
    domain: str,
    extracted_rules: list[dict[str, Any]],
) -> None:
    with trace_regshift_step(
        "policy-graph-extraction",
        session_id,
        domain=domain,
        input_data={"policy_id": policy_id},
        metadata={"rule_count": len(extracted_rules)},
    ) as output:
        output["data"] = {
            "rules": [
                {
                    "id": rule.get("id"),
                    "type": rule.get("type"),
                    "citation": rule.get("citation"),
                }
                for rule in extracted_rules
            ]
        }


def create_langgraph_callback(session_id: str, domain: str | None = None):
    client = _get_client()
    if client is None:
        return None
    try:
        from langfuse.langchain import CallbackHandler

        return CallbackHandler(
            session_id=session_id,
            tags=["regshift", domain or "unknown"],
        )
    except Exception:
        return None
