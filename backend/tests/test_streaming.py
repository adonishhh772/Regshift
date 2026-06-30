import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.database import init_db, get_connection
from app.services.policy_seed import seed_demo_policies

GOLDEN_TEXT = (
    "From next quarter, all purchase orders above £25,000 must require finance approval "
    "before supplier confirmation. The system must log who approved it and block "
    "confirmation if approval is missing."
)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    connection = get_connection()
    connection.execute("DELETE FROM change_sessions")
    connection.execute("DELETE FROM file_index")
    connection.execute("DELETE FROM index_meta")
    connection.commit()
    connection.close()
    seed_demo_policies()
    yield


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


def parse_sse_events(body: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for block in body.split("\n\n"):
        if not block.strip():
            continue
        event_name = "message"
        data_payload = ""
        for line in block.split("\n"):
            if line.startswith("event:"):
                event_name = line[6:].strip()
            elif line.startswith("data:"):
                data_payload = line[5:].strip()
        if data_payload:
            import json

            events.append((event_name, json.loads(data_payload)))
    return events


@pytest.mark.asyncio
async def test_stream_classify_emits_trace_events(client):
    async with client.stream(
        "POST",
        "/api/stream/change/classify",
        json={"text": GOLDEN_TEXT},
        headers={"Accept": "text/event-stream"},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = await response.aread()
        text = body.decode("utf-8")

    events = parse_sse_events(text)
    event_types = [event_type for event_type, _ in events]
    assert "trace" in event_types
    assert "result" in event_types
    assert "done" in event_types

    trace_messages = [payload["message"] for event_type, payload in events if event_type == "trace"]
    assert any("Workflow started" in message for message in trace_messages)
    assert any("Parsed business change" in message for message in trace_messages)
    assert any("Classified domain" in message for message in trace_messages)

    result_payload = next(payload for event_type, payload in events if event_type == "result")
    assert result_payload["domain"] == "procurement"
    assert result_payload["session_id"]


@pytest.mark.asyncio
async def test_stream_agent_completes_when_langfuse_unreachable(client, monkeypatch):
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    monkeypatch.setenv("LANGFUSE_HOST", "http://127.0.0.1:1")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")

    from app.services.langfuse_tracer import disable_langfuse_runtime, reset_langfuse_client

    disable_langfuse_runtime("test setup")

    async with client.stream(
        "POST",
        "/api/stream/workflow/run",
        json={"text": GOLDEN_TEXT},
        headers={"Accept": "text/event-stream"},
    ) as response:
        assert response.status_code == 200
        body = await response.aread()
        text = body.decode("utf-8")

    reset_langfuse_client()
    events = parse_sse_events(text)
    event_types = [event_type for event_type, _ in events]
    assert "trace" in event_types
    assert "result" in event_types
    assert "done" in event_types

    result_payload = next(payload for event_type, payload in events if event_type == "result")
    assert result_payload["status"] in {"paused", "blocked", "completed"}
    assert result_payload["session_id"]
