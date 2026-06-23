from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.pagination import ledger_page
from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.ledger import LedgerPage
from app.schemas.user import MeOut, MeUpdateIn
from app.services import ledger

router = APIRouter(tags=["me"])


def _me_out(db: Session, user: User) -> MeOut:
    return MeOut(
        id=user.id,
        phone=user.phone,
        name=user.name,
        is_verified=user.is_verified,
        balance=ledger.balance(db, user.id),
        available=ledger.available(db, user.id),
        last_active_at=user.last_active_at,
    )


@router.get("/me", response_model=MeOut)
def get_me(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeOut:
    return _me_out(db, user)


@router.patch("/me", response_model=MeOut)
def update_me(
    body: MeUpdateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeOut:
    user.name = body.name
    db.commit()
    db.refresh(user)
    return _me_out(db, user)


@router.get("/me/ledger", response_model=LedgerPage)
def get_ledger(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    cursor: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
) -> LedgerPage:
    return ledger_page(db, user.id, cursor=cursor, limit=limit)
