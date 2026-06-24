"""Contacts adapter — Contacts.framework (CNContactStore) via PyObjC.

Reads return Pointers; writes take ``ContactData``. All access goes through
``runtime.run_native`` (single serialized worker); the store is owned by runtime
(``contacts_store()``), separate from the EKEventStore.
"""

from __future__ import annotations

import Contacts as CN

from ..contracts import ContactData, Pointer
from ..runtime import AccessDenied, contacts_store, run_native

_ENTITY = CN.CNEntityTypeContacts

# Keys fetched for the pointer (name + org) + the stable id. Pointers-not-payload:
# phone/email/postal addresses are NOT fetched by default — a future detail tool can.
_KEYS = [
    CN.CNContactGivenNameKey,
    CN.CNContactFamilyNameKey,
    CN.CNContactOrganizationNameKey,
]

MAX_CONTACTS = 50  # cap the result set (guard against an over-broad name match)


def _contact_summary(c) -> str:
    name = " ".join(p for p in (c.givenName(), c.familyName()) if p).strip()
    org = c.organizationName()
    if name and org:
        return f"{name} — {org}"
    return name or org or "(unnamed contact)"


def _contact_deeplink(ident: str) -> str:
    # addressbook://<id> opens Contacts to the card (best-effort; verify on-device).
    return f"addressbook://{ident}"


def _contact_pointer(c) -> Pointer:
    ident = c.identifier()
    return Pointer(
        id=ident, summary=_contact_summary(c), deeplink=_contact_deeplink(ident)
    )


def _require_access() -> None:
    status = CN.CNContactStore.authorizationStatusForEntityType_(_ENTITY)
    if status != CN.CNAuthorizationStatusAuthorized:
        raise AccessDenied(
            "Contacts access not granted (System Settings → Privacy → Contacts)."
        )


class ContactsAdapter:
    def get_pointers(self, query: str) -> list[Pointer]:
        """query: a name (substring) to match, e.g. 'jane' or 'Jane Doe'."""
        name = query.strip()
        if not name:
            raise ValueError("contacts read needs a name to match (got an empty query)")

        def work():
            cs = contacts_store()
            _require_access()
            pred = CN.CNContact.predicateForContactsMatchingName_(name)
            found, err = cs.unifiedContactsMatchingPredicate_keysToFetch_error_(
                pred, _KEYS, None
            )
            if found is None:
                raise RuntimeError(f"contacts fetch failed: {err}")
            return [_contact_pointer(c) for c in found][:MAX_CONTACTS]

        return run_native(work)

    def create_contact(self, data: ContactData) -> Pointer:
        def work():
            cs = contacts_store()
            _require_access()
            c = CN.CNMutableContact.alloc().init()
            c.setGivenName_(data.given_name)
            if data.family_name is not None:
                c.setFamilyName_(data.family_name)
            if data.organization is not None:
                c.setOrganizationName_(data.organization)
            req = CN.CNSaveRequest.alloc().init()
            req.addContact_toContainerWithIdentifier_(c, None)
            ok, err = cs.executeSaveRequest_error_(req, None)
            if not ok:
                raise RuntimeError(f"save contact failed: {err}")
            return _contact_pointer(c)

        return run_native(work)
