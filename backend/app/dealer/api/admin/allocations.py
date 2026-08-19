"""Allocation batch upload and the allocation register.

The upload is the moment the client's despatch reality enters this system. It
runs in ONE transaction (a half-applied despatch file is worse than a rejected
one) and reports every rejected line by number — the parsing rules and the
reasoning behind them live in services/allocation.py.
"""

import uuid

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import client_ip, get_current_admin, get_db, require_admin_write
from app.core.errors import AppError
from app.dealer.api.admin._common import (
    Pagination,
    allocation_select,
    count_of,
    like,
    pagination,
    to_allocation_out,
)
from app.dealer.models.allocation import Allocation, AllocationBatch
from app.dealer.models.dealer import Dealer
from app.dealer.schemas.admin import (
    AllocationBatchOut,
    AllocationOut,
    AllocationUploadOut,
    BatchRowErrorOut,
    Paginated,
    ReasonIn,
)
from app.dealer.services import allocation as allocation_svc
from app.dealer.services.unitsource import normalise_serial
from app.models.admin import Admin

router = APIRouter(tags=["admin-allocations"])


def _batch_out(batch: AllocationBatch, *, with_errors: bool = True) -> AllocationBatchOut:
    return AllocationBatchOut(
        id=batch.id,
        filename=batch.filename,
        uploaded_by_admin_id=batch.uploaded_by_admin_id,
        row_count=batch.row_count,
        ok_count=batch.ok_count,
        error_count=batch.error_count,
        created_at=batch.created_at,
        errors=(
            [
                BatchRowErrorOut(
                    line=e.line, serial=e.serial, dealer_code=e.dealer_code, reason=e.reason
                )
                for e in allocation_svc.parse_errors(batch)
            ]
            if with_errors
            else []
        ),
    )


@router.post("/allocations/upload", response_model=AllocationUploadOut, status_code=201)
def upload_allocations(
    request: Request,
    file: UploadFile = File(...),
    admin: Admin = Depends(require_admin_write),
    db: Session = Depends(get_db),
) -> AllocationUploadOut:
    """Upload a despatch CSV: columns serial, dealer_code and optional dispatch_ref.

    Read synchronously off the SpooledTemporaryFile rather than awaited: every
    other router here is sync and runs in the threadpool, and mixing the two
    styles for one endpoint buys nothing.
    """
    content = file.file.read(allocation_svc.MAX_UPLOAD_BYTES + 1)
    if not content:
        raise AppError("empty_file", 400, "The uploaded file is empty")

    result = allocation_svc.upload_csv(
        db,
        content=content,
        filename=file.filename,
        admin_id=admin.id,
        ip=client_ip(request),
    )
    # One commit for the whole file — see the service docstring.
    db.commit()

    return AllocationUploadOut(
        batch=_batch_out(result.batch, with_errors=False),
        created_count=result.created_count,
        unchanged_count=result.unchanged_count,
        errors=[
            BatchRowErrorOut(
                line=e.line, serial=e.serial, dealer_code=e.dealer_code, reason=e.reason
            )
            for e in result.errors
        ],
    )


@router.post("/allocations/preview", response_model=AllocationUploadOut)
def preview_allocations(
    request: Request,
    file: UploadFile = File(...),
    admin: Admin = Depends(require_admin_write),
    db: Session = Depends(get_db),
) -> AllocationUploadOut:
    """Dry run: report exactly what an upload would do, and write nothing.

    This deliberately runs the REAL apply path and then rolls back, rather than
    reimplementing the validation. A preview that uses different logic from the
    apply is worse than no preview at all — it would eventually disagree, and the
    operator would trust the wrong one. Rolling back a transaction that already
    did the work is the only way to guarantee they agree.

    Worth it because a despatch file is thousands of rows: an operator needs to
    see "412 new, 3,588 unchanged, 6 rejected" before committing to it.
    """
    content = file.file.read(allocation_svc.MAX_UPLOAD_BYTES + 1)
    if not content:
        raise AppError("empty_file", 400, "The uploaded file is empty")

    try:
        result = allocation_svc.upload_csv(
            db,
            content=content,
            filename=file.filename,
            admin_id=admin.id,
            ip=client_ip(request),
        )
        out = AllocationUploadOut(
            batch=_batch_out(result.batch, with_errors=False),
            created_count=result.created_count,
            unchanged_count=result.unchanged_count,
                errors=[
                BatchRowErrorOut(
                    line=e.line, serial=e.serial, dealer_code=e.dealer_code, reason=e.reason
                )
                for e in result.errors
            ],
        )
        # Build the response BEFORE rolling back: the ORM objects it reads from
        # are detached and unusable afterwards.
        out = AllocationUploadOut.model_validate(out.model_dump())
    finally:
        db.rollback()

    return out


@router.get("/allocations", response_model=Paginated[AllocationOut])
def list_allocations(
    dealer_id: uuid.UUID | None = None,
    dealer_code: str | None = Query(default=None, max_length=32),
    status: str | None = Query(
        default=None, pattern="^(allocated|registered|revoked|returned)$"
    ),
    serial: str | None = Query(default=None, max_length=200),
    batch_id: uuid.UUID | None = None,
    page: Pagination = Depends(pagination),
    _: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Paginated[AllocationOut]:
    stmt = allocation_select()
    if dealer_id:
        stmt = stmt.where(Allocation.dealer_id == dealer_id)
    if dealer_code:
        stmt = stmt.where(Dealer.code.ilike(like(dealer_code)))
    if status:
        stmt = stmt.where(Allocation.status == status)
    if serial:
        # Normalised first so a pasted QR URL finds the same row the scanner
        # created. Falls back to a partial match for a half-remembered serial.
        needle = normalise_serial(serial)
        stmt = stmt.where(Allocation.serial.ilike(like(needle or serial)))
    if batch_id:
        stmt = stmt.where(Allocation.batch_id == batch_id)

    total = count_of(db, stmt)
    rows = db.execute(
        stmt.order_by(Allocation.allocated_at.desc()).limit(page.limit).offset(page.offset)
    ).all()
    return Paginated[AllocationOut](
        items=[to_allocation_out(row) for row in rows],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/allocations/batches", response_model=Paginated[AllocationBatchOut])
def list_batches(
    page: Pagination = Depends(pagination),
    _: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Paginated[AllocationBatchOut]:
    stmt = select(AllocationBatch)
    total = count_of(db, stmt)
    batches = db.execute(
        stmt.order_by(AllocationBatch.created_at.desc()).limit(page.limit).offset(page.offset)
    ).scalars()
    # Error detail is per-batch and can be long; the list shows counts only.
    return Paginated[AllocationBatchOut](
        items=[_batch_out(b, with_errors=False) for b in batches],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/allocations/batches/{batch_id}", response_model=AllocationBatchOut)
def get_batch(
    batch_id: uuid.UUID,
    _: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> AllocationBatchOut:
    batch = db.get(AllocationBatch, batch_id)
    if batch is None:
        raise AppError("batch_not_found", 404, "No such upload")
    return _batch_out(batch)


@router.post("/allocations/{allocation_id}/revoke", response_model=AllocationOut)
def revoke_allocation(
    allocation_id: uuid.UUID,
    body: ReasonIn,
    request: Request,
    admin: Admin = Depends(require_admin_write),
    db: Session = Depends(get_db),
) -> AllocationOut:
    allocation = db.get(Allocation, allocation_id)
    if allocation is None:
        raise AppError("allocation_not_found", 404, "No such allocation")

    allocation_svc.revoke(
        db,
        allocation=allocation,
        reason=body.reason,
        admin_id=admin.id,
        ip=client_ip(request),
    )
    db.commit()

    row = db.execute(
        allocation_select().where(Allocation.id == allocation_id)
    ).one()
    return to_allocation_out(row)
