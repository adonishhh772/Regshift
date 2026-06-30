import asyncio
import json
import logging
import threading
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from app.models.schemas import AgentTraceEvent, TraceStatus
from app.trace import reset_trace_stream_listener, set_trace_stream_listener

logger = logging.getLogger(__name__)

SSE_OPEN_PADDING = ": regshift-stream-open " + (" " * 2048) + "\n\n"


def format_sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def build_stream_ready_event() -> dict[str, Any]:
    return AgentTraceEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        message="Workflow started",
        status=TraceStatus.COMPLETED,
        explanation="Backend assurance pipeline connected",
    ).model_dump()


def normalize_stream_error_detail(detail: Any) -> str:
    if detail is None:
        return "Workflow step failed"
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        return json.dumps(detail, default=str)
    if isinstance(detail, dict):
        for key in ("message", "msg", "error", "detail"):
            value = detail.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return json.dumps(detail, default=str)
    return str(detail)


async def sse_event_generator(handler: Callable[[], Any]) -> AsyncIterator[str]:
    queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def on_trace(event: Any) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, ("trace", event.model_dump()))

    def run_sync_handler() -> None:
        token = set_trace_stream_listener(on_trace)
        handler_name = getattr(handler, "__name__", handler.__class__.__name__)
        logger.info("Stream workflow started handler=%s", handler_name)
        try:
            result = handler()
            if hasattr(result, "model_dump"):
                payload = result.model_dump()
            elif isinstance(result, dict):
                payload = result
            else:
                payload = {"value": result}
            logger.info(
                "Stream workflow completed handler=%s session_id=%s",
                handler_name,
                payload.get("session_id") if isinstance(payload, dict) else None,
            )
            loop.call_soon_threadsafe(queue.put_nowait, ("result", payload))
        except HTTPException as error:
            logger.warning("Stream workflow HTTP error: %s", error.detail)
            loop.call_soon_threadsafe(
                queue.put_nowait,
                (
                    "error",
                    {
                        "status_code": error.status_code,
                        "detail": normalize_stream_error_detail(error.detail),
                    },
                ),
            )
        except Exception as error:
            logger.exception("Stream workflow failed")
            loop.call_soon_threadsafe(
                queue.put_nowait,
                (
                    "error",
                    {"status_code": 500, "detail": normalize_stream_error_detail(error)},
                ),
            )
        finally:
            reset_trace_stream_listener(token)
            loop.call_soon_threadsafe(queue.put_nowait, ("done", {}))

    yield SSE_OPEN_PADDING
    yield format_sse("trace", build_stream_ready_event())
    await asyncio.sleep(0)

    worker = threading.Thread(target=run_sync_handler, daemon=True)
    worker.start()

    while True:
        event_type, data = await queue.get()
        yield format_sse(event_type, data)
        await asyncio.sleep(0)
        if event_type in ("done", "error"):
            break


def create_sse_response(handler: Callable[[], Any]) -> StreamingResponse:
    return StreamingResponse(
        sse_event_generator(handler),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
