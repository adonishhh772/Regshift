from collections.abc import Callable
from contextvars import ContextVar, Token
from datetime import datetime, timezone
import logging

from app.models.schemas import AgentTraceEvent, TraceStatus

logger = logging.getLogger(__name__)

TraceStreamListener = Callable[[AgentTraceEvent], None]

_trace_stream_listener: ContextVar[TraceStreamListener | None] = ContextVar(
    "trace_stream_listener",
    default=None,
)


def set_trace_stream_listener(listener: TraceStreamListener | None) -> Token:
    return _trace_stream_listener.set(listener)


def reset_trace_stream_listener(token: Token) -> None:
    _trace_stream_listener.reset(token)


class TraceLogger:
    def __init__(self) -> None:
        self._events: list[AgentTraceEvent] = []

    def emit(
        self,
        message: str,
        status: TraceStatus = TraceStatus.COMPLETED,
        explanation: str | None = None,
        evidence_count: int | None = None,
    ) -> AgentTraceEvent:
        event = AgentTraceEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            message=message,
            status=status,
            explanation=explanation,
            evidence_count=evidence_count,
        )
        self._events.append(event)
        listener = _trace_stream_listener.get()
        if listener is not None:
            listener(event)
        logger.info(
            "Workflow trace status=%s message=%s%s",
            status.value,
            message,
            f" explanation={explanation}" if explanation else "",
        )
        return event

    def get_events(self) -> list[AgentTraceEvent]:
        return list(self._events)

    def clear(self) -> None:
        self._events.clear()
