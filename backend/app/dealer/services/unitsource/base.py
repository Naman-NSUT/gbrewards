"""How the dealer side learns about physical units.

The dealer programme owns its serials outright. `dealer_units` rows are created
by QR batch generation in the DEALER admin panel and scanned by the dealer app —
they are unrelated to the worker programme's `product_units`, and neither token
can be derived from the other. A mattress carries two labels, one per programme.

The interface stays because it is a useful seam, not because anything remote is
behind it: reading a unit is a local join, and it cannot fail for network
reasons. UnitSourceUnavailable therefore never fires today.

The consequence to keep in mind: nothing here knows whether the factory ever
assembled the unit. This registry is authoritative for the dealer programme and
knows nothing about the other one.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


def normalise_serial(raw: str) -> str:
    """Turn whatever the camera decoded into the canonical serial.

    The dealer QR carries a bare UUIDv4 (see app/dealer/services/qr.py), printed
    in Courier beneath the code so a scuffed label can still be typed in. A URL
    is stripped to its last path segment anyway: if the label format ever changes
    that is the one alteration that would silently break every scanner, and being
    immune to it costs two lines. Comparison is lowercased, because a human
    retyping from a label will not match case.
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
    # 'active' or 'void' in the dealer registry. NOT a sale status — whether a
    # unit has been sold is warranties.status.
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
