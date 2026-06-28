"""Mail adapter — Mail.app via osascript (Automation TCC). Read-only v1: inbox search.

Mail has a rich AppleScript dictionary. ``Pointer.id`` is the RFC822 ``message id``
(stable across relaunch — the citation contract), not the AppleScript object id.
Pointers, not bodies — the body is never fetched. Subject-search over the inbox; Mail's
AppleScript is slow on large mailboxes, so results are capped and the osascript timeout
bounds a pathological search. User input goes via argv (no script injection).
"""

from __future__ import annotations

from ..contracts import Pointer
from ..runtime import run_osascript

MAX_MAILS = 25

_SEARCH = """on run argv
  set q to item 1 of argv
  set out to ""
  tell application "Mail"
    repeat with m in (messages of inbox whose subject contains q)
      set out to out & (message id of m) & tab
      set out to out & (subject of m) & tab & (sender of m) & linefeed
    end repeat
  end tell
  return out
end run"""


def _summary(subject: str, sender: str) -> str:
    subject, sender = subject.strip(), sender.strip()
    if subject and sender:
        return f"{subject} — {sender}"
    return subject or sender or "(no subject)"


def _deeplink(message_id: str) -> str:
    # message://%3c<id>%3e opens the message in Mail (best-effort; verify on-device).
    mid = message_id.strip().lstrip("<").rstrip(">")
    return f"message://%3c{mid}%3e"


def _parse(raw: str) -> list[Pointer]:
    out = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        mid = parts[0]
        subject = parts[1] if len(parts) > 1 else ""
        sender = parts[2] if len(parts) > 2 else ""
        out.append(
            Pointer(id=mid, summary=_summary(subject, sender), deeplink=_deeplink(mid))
        )
    return out


class MailAdapter:
    def get_pointers(self, query: str) -> list[Pointer]:
        """query: a subject substring to find in the inbox."""
        q = query.strip()
        if not q:
            raise ValueError("mail read needs a subject substring (got an empty query)")
        return _parse(run_osascript(_SEARCH, q))[:MAX_MAILS]
