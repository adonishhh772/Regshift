import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from contextlib import contextmanager
from typing import Any, Callable, Generator

from app.config import settings

logger = logging.getLogger(__name__)

_client = None
_auth_cache: dict[str, Any] | None = None
_langfuse_runtime_disabled = False
_client_lock = threading.Lock()

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

_LANGFUSE_AUTH_TIMEOUT_SECONDS = 5.0
_LANGFUSE_FLUSH_TIMEOUT_SECONDS = 2.0
_LANGFUSE_SPAN_TIMEOUT_SECONDS = 2.0
_LANGFUSE_PROBE_MAX_ATTEMPTS = 12
_LANGFUSE_PROBE_DELAY_SECONDS = 5.0


def _configure_otel_export_limits() -> None:
    import os

    os.environ.setdefault("OTEL_EXPORTER_OTLP_TIMEOUT", "2000")
    os.environ.setdefault("OTEL_BSP_EXPORT_TIMEOUT", "2000")
    os.environ.setdefault("OTEL_BSP_SCHEDULE_DELAY", "5000")


def _run_with_timeout(action: Callable[[], Any], timeout_seconds: float) -> bool:
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(action)
    try:
        future.result(timeout=timeout_seconds)
        return True
    except FuturesTimeoutError:
        return False
    except Exception:
        return False
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _safe_langfuse_operation(action_name: str, action: Callable[[], Any]) -> bool:
    completed = _run_with_timeout(action, _LANGFUSE_SPAN_TIMEOUT_SECONDS)
    if completed:
        return True
    logger.warning(
        "Langfuse %s timed out after %.1fs — disabling export",
        action_name,
        _LANGFUSE_SPAN_TIMEOUT_SECONDS,
    )
    disable_langfuse_runtime(f"Langfuse {action_name} timed out")
    return False


def _reset_client_unlocked() -> None:
    global _client, _auth_cache
    client_to_close = _client
    if client_to_close is not None:
        _run_with_timeout(client_to_close.flush, _LANGFUSE_FLUSH_TIMEOUT_SECONDS)
        _run_with_timeout(client_to_close.shutdown, _LANGFUSE_FLUSH_TIMEOUT_SECONDS)
    _client = None
    _auth_cache = None


def reset_langfuse_client() -> None:
    with _client_lock:
        _reset_client_unlocked()


def disable_langfuse_runtime(reason: str | None = None) -> None:
    global _langfuse_runtime_disabled, _auth_cache
    with _client_lock:
        _langfuse_runtime_disabled = True
        _reset_client_unlocked()
        _auth_cache = {
            "authenticated": False,
            "reason": reason or "Langfuse unavailable; workflow tracing continues without export",
        }


def probe_langfuse_connectivity() -> dict[str, Any]:
    return probe_langfuse_connectivity_with_retry()


def probe_langfuse_connectivity_with_retry(
    max_attempts: int = _LANGFUSE_PROBE_MAX_ATTEMPTS,
    delay_seconds: float = _LANGFUSE_PROBE_DELAY_SECONDS,
) -> dict[str, Any]:
    if not settings.langfuse_enabled:
        logger.info("Langfuse tracing disabled by configuration")
        return {"authenticated": False, "reason": "Langfuse disabled"}

    last_result: dict[str, Any] = {"authenticated": False, "reason": "Langfuse not probed"}
    for attempt in range(1, max_attempts + 1):
        last_result = verify_langfuse_connection()
        if last_result.get("authenticated"):
            logger.info(
                "Langfuse connected host=%s attempt=%s/%s",
                settings.langfuse_host,
                attempt,
                max_attempts,
            )
            return last_result

        logger.warning(
            "Langfuse probe failed host=%s attempt=%s/%s reason=%s",
            settings.langfuse_host,
            attempt,
            max_attempts,
            last_result.get("reason"),
        )
        if attempt < max_attempts:
            time.sleep(delay_seconds)

    disable_langfuse_runtime(str(last_result.get("reason", "Langfuse unreachable after retries")))
    logger.error(
        "Langfuse runtime disabled after %s attempts host=%s reason=%s",
        max_attempts,
        settings.langfuse_host,
        last_result.get("reason"),
    )
    return last_result


def _auth_check_with_timeout() -> dict[str, Any]:
    global _auth_cache
    if not settings.langfuse_enabled:
        return {"authenticated": False, "reason": "Langfuse disabled"}
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return {"authenticated": False, "reason": "Missing Langfuse API keys"}

    client = _get_client(force_refresh=True)
    if client is None:
        reason = (_auth_cache or {}).get("reason", "Failed to initialize Langfuse client")
        return {"authenticated": False, "reason": reason}

    _auth_cache = {"authenticated": True}
    return _auth_cache


def verify_langfuse_connection() -> dict[str, Any]:
    global _langfuse_runtime_disabled
    with _client_lock:
        _langfuse_runtime_disabled = False
    reset_langfuse_client()
    return _auth_check_with_timeout()


def _build_langfuse_client() -> Any:
    _configure_otel_export_limits()
    from langfuse import Langfuse

    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
        flush_at=50,
        flush_interval=10,
    )


def _initialize_client_with_auth() -> bool:
    global _client, _auth_cache
    candidate: Any | None = None
    try:
        candidate = _build_langfuse_client()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(candidate.auth_check)
            future.result(timeout=_LANGFUSE_AUTH_TIMEOUT_SECONDS)
        _client = candidate
        _auth_cache = {"authenticated": True}
        return True
    except FuturesTimeoutError:
        _auth_cache = {"authenticated": False, "reason": "Langfuse auth check timed out"}
        logger.warning("Langfuse auth check timed out host=%s", settings.langfuse_host)
    except Exception as error:
        _auth_cache = {"authenticated": False, "reason": str(error)}
        logger.warning("Langfuse auth check failed host=%s error=%s", settings.langfuse_host, error)
    finally:
        if _client is None and candidate is not None:
            _run_with_timeout(candidate.shutdown, _LANGFUSE_FLUSH_TIMEOUT_SECONDS)
    return False


def _get_client(*, force_refresh: bool = False):
    global _client, _langfuse_runtime_disabled
    with _client_lock:
        if force_refresh:
            _reset_client_unlocked()
        if _langfuse_runtime_disabled and not force_refresh:
            return None
        if _client is not None:
            return _client
        if not settings.langfuse_enabled:
            return None
        if not settings.langfuse_public_key or not settings.langfuse_secret_key:
            return None
        if _initialize_client_with_auth():
            logger.info("Langfuse client initialized host=%s", settings.langfuse_host)
            return _client
        return None


def langfuse_status() -> dict[str, Any]:
    base_status = {
        "enabled": settings.langfuse_enabled,
        "host": settings.langfuse_host,
        "ui_url": settings.langfuse_ui_url,
        "project_id": settings.langfuse_project_id,
    }
    if not settings.langfuse_enabled:
        return {**base_status, "available": False, "authenticated": False}

    if _langfuse_runtime_disabled:
        return {
            **base_status,
            "available": False,
            "authenticated": False,
            "auth_error": (_auth_cache or {}).get("reason", "Langfuse runtime disabled"),
        }

    client = _get_client()
    configured = client is not None
    authenticated = bool(_auth_cache and _auth_cache.get("authenticated"))
    return {
        **base_status,
        "available": configured,
        "authenticated": authenticated,
        "auth_error": None if authenticated else (_auth_cache or {}).get("reason"),
    }


def flush_traces() -> None:
    client = _get_client()
    if client is None:
        logger.debug("Langfuse flush skipped — client unavailable")
        return
    logger.debug("Langfuse flushing trace batch")
    if not _run_with_timeout(client.flush, _LANGFUSE_FLUSH_TIMEOUT_SECONDS):
        logger.warning("Langfuse flush timed out — disabling export")
        disable_langfuse_runtime("Langfuse flush timed out")


def build_session_trace_url(session_id: str) -> str | None:
    if not settings.langfuse_ui_url:
        return None
    base_url = settings.langfuse_ui_url.rstrip("/")
    project_id = settings.langfuse_project_id
    return f"{base_url}/project/{project_id}/traces?search={session_id}"


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
    propagate_cm = propagate_attributes(
        session_id=session_id,
        trace_name=TRACE_NAME_REGSHIFT,
        tags=tags,
        metadata={"domain": domain or "unknown", "step": step_name},
    )
    propagate_cm.__enter__()
    span_cm = client.start_as_current_observation(
        as_type="span",
        name=step_name,
        input=input_data or {},
        metadata=span_metadata,
    )
    span = span_cm.__enter__()
    step_error: BaseException | None = None
    try:
        yield output_holder
    except BaseException as error:
        step_error = error
        raise
    finally:
        if step_error is None:
            _safe_langfuse_operation(
                f"span update ({step_name})",
                lambda: span.update(
                    output=output_holder.get("data", {}),
                    metadata={**span_metadata, "status": output_holder.get("status", "completed")},
                ),
            )
        else:
            _safe_langfuse_operation(
                f"span error update ({step_name})",
                lambda: span.update(
                    output={"error": str(step_error)},
                    metadata={**span_metadata, "status": "error"},
                ),
            )
        _safe_langfuse_operation(
            f"span close ({step_name})",
            lambda: span_cm.__exit__(type(step_error), step_error, step_error.__traceback__ if step_error else None),
        )
        _safe_langfuse_operation(
            "propagate close",
            lambda: propagate_cm.__exit__(type(step_error), step_error, step_error.__traceback__ if step_error else None),
        )


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

    span_cm = client.start_as_current_observation(
        as_type="span",
        name=step_name,
        input=input_data or {},
        metadata={"workflow_step": step_name, **(metadata or {})},
    )
    span = span_cm.__enter__()
    step_error: BaseException | None = None
    try:
        yield output_holder
    except BaseException as error:
        step_error = error
        raise
    finally:
        if step_error is None:
            _safe_langfuse_operation(
                f"nested span update ({step_name})",
                lambda: span.update(output=output_holder.get("data", {})),
            )
        else:
            _safe_langfuse_operation(
                f"nested span error update ({step_name})",
                lambda: span.update(output={"error": str(step_error)}),
            )
        _safe_langfuse_operation(
            f"nested span close ({step_name})",
            lambda: span_cm.__exit__(type(step_error), step_error, step_error.__traceback__ if step_error else None),
        )


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
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
            session_id=session_id,
            tags=["regshift", domain or "unknown"],
        )
    except Exception:
        return None
