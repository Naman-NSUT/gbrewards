"""Serve the invoice behind a customer self-registration.

A self-registration is an anonymous claim that a sale happened, and the invoice
photo is the ONLY evidence for it. Until this endpoint existed nothing could
read a stored proof back: `storage.path_for` was reachable only from `discard`,
the queue rendered the raw object key as text, and the person deciding a
five-year warranty obligation was judging it blind.

Its own module rather than another route on warranties.py because it is the one
admin endpoint that returns bytes instead of JSON, with its own headers, its own
failure modes and its own reason to exist.

Read-level auth, matching list_approvals. Support staff work the queue all day
and must be able to SEE the evidence; `require_admin_write` guards ACTING on it
(approve/reject), which is the decision that moves money and warranty term.
"""

import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_dealer_admin, get_db
from app.core.errors import AppError
from app.dealer.models.admin import DealerAdmin as Admin
from app.dealer.models.warranty import Warranty
from app.dealer.services import storage

router = APIRouter(tags=["admin-approvals"])


@router.get(
    "/warranties/{warranty_id}/proof",
    response_class=Response,
    responses={
        200: {"content": {kind: {} for kind in storage.SERVED_CONTENT_TYPES}},
    },
)
def get_warranty_proof(
    warranty_id: uuid.UUID,
    _: Admin = Depends(get_current_dealer_admin),
    db: Session = Depends(get_db),
) -> Response:
    """The stored invoice for one warranty, as bytes.

    Addressed by WARRANTY id, never by file name: the caller cannot name a file,
    so the only key that can be reached is the one this warranty's own row
    carries. `storage.path_for` still re-checks it, because that key round-trips
    through a database column and a value is not safe merely because it came
    back from somewhere we wrote it.
    """
    warranty = db.get(Warranty, warranty_id)
    if warranty is None:
        raise AppError("warranty_not_found", 404, "No such warranty")
    if not warranty.proof_file_key:
        # A backdate request has no proof by design, and so does a warranty the
        # dealer registered. Distinct from proof_missing below.
        raise AppError("no_proof", 404, "No invoice was attached to this warranty")

    proof = storage.load(warranty.proof_file_key)
    return Response(
        content=proof.data,
        media_type=proof.content_type,
        headers={
            # inline: the approver wants to LOOK at the invoice next to the
            # decision, not collect a downloads folder full of them.
            "Content-Disposition": f'inline; filename="proof-{warranty_id}{proof.extension}"',
            # The content type comes from our own whitelist, so tell the browser
            # to take it literally. Without this a file that slipped past the
            # sniffer could be re-guessed as HTML and run on the admin's origin.
            "X-Content-Type-Options": "nosniff",
            # A customer's invoice carries their name, address and purchase.
            # It must not sit in a shared proxy, a browser cache, or on the
            # disk of whichever machine the approver happened to use.
            "Cache-Control": "private, no-store",
        },
    )
