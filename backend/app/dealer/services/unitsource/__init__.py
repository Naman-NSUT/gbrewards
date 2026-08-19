from sqlalchemy.orm import Session

from app.dealer.services.unitsource.base import (
    UnitFacts,
    UnitSource,
    UnitSourceUnavailable,
    normalise_serial,
)
from app.dealer.services.unitsource.local import LocalUnitSource


def get_unit_source(session: Session) -> UnitSource:
    return LocalUnitSource(session)


__all__ = [
    "LocalUnitSource",
    "UnitFacts",
    "UnitSource",
    "UnitSourceUnavailable",
    "get_unit_source",
    "normalise_serial",
]
