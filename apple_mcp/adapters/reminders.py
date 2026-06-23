"""Reminders adapter — EventKit via PyObjC.

STUB. Implemented in v1 (see GitHub issues). Reads return Pointers; writes take ``ReminderData``.
All EventKit access MUST go through ``runtime.run_native`` (single serialized worker thread).
"""

from __future__ import annotations

from ..contracts import Pointer, ReminderData


class RemindersAdapter:
    # ponytail: create the EKEventStore on runtime's single worker at __init__ + request TCC there.
    def get_pointers(self, query: str) -> list[Pointer]:
        raise NotImplementedError("v1: EventKit reminders read — see GitHub issues")

    def create_reminder(self, data: ReminderData) -> Pointer:
        raise NotImplementedError("v1: EventKit reminders write — see GitHub issues")
