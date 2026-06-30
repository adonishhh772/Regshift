import time

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.langfuse_tracer import disable_langfuse_runtime, langfuse_status, reset_langfuse_client, verify_langfuse_connection


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


@pytest.mark.asyncio
async def test_langfuse_refresh_endpoint(client, monkeypatch):
    monkeypatch.setenv("LANGFUSE_ENABLED", "false")
    reset_langfuse_client()

    response = await client.post("/api/langfuse/refresh")
    assert response.status_code == 200
    body = response.json()
    assert body["authenticated"] is False
    assert body["langfuse"]["enabled"] is False


def test_langfuse_status_includes_auth_fields(monkeypatch):
    monkeypatch.setenv("LANGFUSE_ENABLED", "false")
    reset_langfuse_client()
    status = langfuse_status()
    assert "authenticated" in status
    assert status["authenticated"] is False


def test_verify_langfuse_connection_when_disabled(monkeypatch):
    monkeypatch.setenv("LANGFUSE_ENABLED", "false")
    reset_langfuse_client()
    result = verify_langfuse_connection()
    assert result["authenticated"] is False


def test_disable_langfuse_runtime_blocks_client_creation(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "langfuse_enabled", True)
    monkeypatch.setattr(settings, "langfuse_public_key", "pk-test")
    monkeypatch.setattr(settings, "langfuse_secret_key", "sk-test")
    reset_langfuse_client()
    disable_langfuse_runtime("Langfuse host unreachable")

    status = langfuse_status()
    assert status["enabled"] is True
    assert status["available"] is False
    assert status["authenticated"] is False
    assert status["auth_error"] == "Langfuse host unreachable"


def test_flush_traces_disables_runtime_on_timeout(monkeypatch):
    from app.services import langfuse_tracer

    class SlowClient:
        def flush(self) -> None:
            time.sleep(5)

    monkeypatch.setattr(langfuse_tracer, "_get_client", lambda: SlowClient())
    monkeypatch.setattr(langfuse_tracer, "_langfuse_runtime_disabled", False)
    reset_langfuse_client()

    langfuse_tracer.flush_traces()

    assert langfuse_tracer._langfuse_runtime_disabled is True
    status = langfuse_status()
    assert status["available"] is False


def test_probe_langfuse_retries_before_disabling(monkeypatch):
    from app.services import langfuse_tracer

    attempts = {"count": 0}

    def fake_verify() -> dict[str, str | bool]:
        attempts["count"] += 1
        if attempts["count"] < 3:
            return {"authenticated": False, "reason": "temporary failure"}
        return {"authenticated": True}

    monkeypatch.setattr(langfuse_tracer, "verify_langfuse_connection", fake_verify)
    monkeypatch.setattr(langfuse_tracer.settings, "langfuse_enabled", True)
    monkeypatch.setattr(langfuse_tracer.time, "sleep", lambda *_args, **_kwargs: None)
    reset_langfuse_client()

    result = langfuse_tracer.probe_langfuse_connectivity_with_retry(max_attempts=3, delay_seconds=0)

    assert result["authenticated"] is True
    assert attempts["count"] == 3
