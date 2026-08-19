"""How the dealer side learns about physical units.

HISTORY, because it explains the shape of this file. Dealer Rewards was first
built as a separate service that could not share a database with GB Rewards, so
this was an interface over a local mirror with a live read-through and a defined
staleness tolerance. That constraint was lifted: both systems now live in one
repo, on one backend, against one database.

So the answer is now the simplest possible one — read `product_units` directly.
The interface survives because it is what made the change cheap: swapping a
networked mirror for a local read was one new implementation and no change to
registration logic. It also keeps the seam if the two are ever split again.

What has NOT changed is the ownership rule. The manufacturing side owns the unit:
`product_units` rows are created by QR batch generation in the worker admin, and
the dealer side only ever READS them. Nothing under app/dealer/ inserts or
updates a product_unit.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


def normalise_serial(raw: str) -> str:
    """Turn whatever the camera decoded into the canonical serial.

    The QR carries a bare UUIDv4 today (see services/qr.py — `qrcode.make` is
    handed `unit.token` directly, and the same value is printed in Courier under
    the code so a scuffed label can be typed in). We still strip a URL down to
    its last path segment, because that is the one format change that would
    silently break every scanner, and it costs two lines to be immune to it.
    Comparison is lowercased: a human retyping from the label will not match case.
    """
    value = (raw or "").strip()
    if not value:
        return ""
    if "://" in value:
        value = value.split("?", 1)[0].split("#", 1)[0]
        segments = [s for s in value.split("/") if s]
        if segments:
            value = segments[-1]
    return value.lower()


@dataclass(frozen=True)
class UnitFacts:
    """What we need to know about a physical unit to register a warranty."""

    serial: str
    product_id: Any
    model_name: str | None
    model_code: str | None
    warranty_months: int | None
    # The manufacturing lifecycle value: 'active' | 'claimed' | 'void'.
    #
    # THIS IS NOT A SALE STATUS. A factory worker scanning the mattress during
    # assembly sets it to 'claimed' months before it reaches a shop floor, so
    # 'claimed' says nothing about whether the unit has been sold to anyone.
    # Conflating the two would make every assembled mattress look sold.
    source_status: str | None
    verified: bool
    raw: dict[str, Any] | None = None


class UnitSourceUnavailable(Exception):
    """Kept for the interface's sake; a local database read cannot raise it.

    Callers still handle it, so that splitting the services apart again does not
    require revisiting every call site.
    """


class UnitSource(ABC):
    @abstractmethod
    def get(self, serial: str) -> UnitFacts | None:
        """Facts for a serial, or None if no such unit exists."""
