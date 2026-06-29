from datetime import datetime, timezone

from app.models.schemas import AgentTraceEvent, TraceStatus


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
        return event

    def get_events(self) -> list[AgentTraceEvent]:
        return list(self._events)

    def clear(self) -> None:
        self._events.clear()
