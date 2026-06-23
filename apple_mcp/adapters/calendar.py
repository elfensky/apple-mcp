"""Calendar adapter — EventKit via PyObjC.

STUB. Implemented in v1 (see GitHub issues). Reads return Pointers; writes take ``CalendarEventData``.
All EventKit access MUST go through ``runtime.run_native`` (single serialized worker thread).
"""

from __future__ import annotations

from ..contracts import CalendarEventData, Pointer


class CalendarAdapter:
    # ponytail: share the EKEventStore created by the reminders adapter (one store, one thread).
    def get_pointers(self, query: str) -> list[Pointer]:
        raise NotImplementedError("v1: EventKit calendar read — see GitHub issues")

    def create_event(self, data: CalendarEventData) -> Pointer:
        raise NotImplementedError("v1: EventKit calendar write — see GitHub issues")
