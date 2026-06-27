"""Contacts adapter — Contacts.app via AppleScript/osascript (Automation TCC).

Reads return Pointers; writes take ``ContactData``. Uses the osascript escape hatch
(``runtime.run_osascript``), NOT the Contacts framework: a non-bundled server can't get
``CNContactStore`` TCC (no usage-description bundle), but Automation TCC — scripting
Contacts.app — works, attributed to the responsible host app. See issue #15.

User input is passed as ``osascript`` argv (``on run argv``), not interpolated into
the script, so a name or id can't break out of the AppleScript.
"""

from __future__ import annotations

from ..contracts import ContactData, Pointer
from ..runtime import run_osascript

MAX_CONTACTS = 50  # cap a broad name match

# Each matching person -> "id<TAB>name<TAB>org<TAB>phone<TAB>email" line. Unset fields
# (`missing value` / no phones / no emails) normalize to "". Phone/email are the first
# of each — a citable handle to *reach* the person, not the full card.
_SEARCH = """on run argv
  set q to item 1 of argv
  set out to ""
  tell application "Contacts"
    repeat with p in (people whose name contains q)
      set theOrg to organization of p
      if theOrg is missing value then set theOrg to ""
      set thePhone to ""
      if (count of phones of p) > 0 then set thePhone to value of item 1 of phones of p
      set theEmail to ""
      if (count of emails of p) > 0 then set theEmail to value of item 1 of emails of p
      set out to out & (id of p) & tab & (name of p) & tab & theOrg
      set out to out & tab & thePhone & tab & theEmail & linefeed
    end repeat
  end tell
  return out
end run"""

_CREATE = """on run argv
  set fn to item 1 of argv
  set ln to item 2 of argv
  set org to item 3 of argv
  tell application "Contacts"
    set p to make new person with properties {first name:fn}
    if ln is not "" then set last name of p to ln
    if org is not "" then set organization of p to org
    save
    return id of p
  end tell
end run"""


def _summary(name: str, org: str, phone: str = "", email: str = "") -> str:
    name, org = name.strip(), org.strip()
    head = f"{name} — {org}" if (name and org) else (name or org)
    contact = " · ".join(x for x in (phone.strip(), email.strip()) if x)
    if head and contact:
        return f"{head} · {contact}"
    return head or contact or "(unnamed contact)"


def _deeplink(ident: str) -> str:
    # addressbook://<id> opens Contacts to the card (best-effort; verify on-device).
    return f"addressbook://{ident}"


def _parse(raw: str) -> list[Pointer]:
    out = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        ident = parts[0]
        name = parts[1] if len(parts) > 1 else ""
        org = parts[2] if len(parts) > 2 else ""
        phone = parts[3] if len(parts) > 3 else ""
        email = parts[4] if len(parts) > 4 else ""
        out.append(
            Pointer(
                id=ident,
                summary=_summary(name, org, phone, email),
                deeplink=_deeplink(ident),
            )
        )
    return out


class ContactsAdapter:
    def get_pointers(self, query: str) -> list[Pointer]:
        """query: a name (substring) to match, e.g. 'jane' or 'Jane Doe'."""
        name = query.strip()
        if not name:
            raise ValueError("contacts read needs a name to match (got an empty query)")
        return _parse(run_osascript(_SEARCH, name))[:MAX_CONTACTS]

    def create_contact(self, data: ContactData) -> Pointer:
        ident = run_osascript(
            _CREATE, data.given_name, data.family_name or "", data.organization or ""
        ).strip()
        full = f"{data.given_name} {data.family_name or ''}"
        return Pointer(
            id=ident,
            summary=_summary(full, data.organization or ""),
            deeplink=_deeplink(ident),
        )
