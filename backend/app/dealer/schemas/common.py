import re
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Indian mobile numbers, normalised to E.164. Accepting "9812345678",
# "09812345678", "+91 98123 45678" and storing one canonical form is the
# difference between a customer finding their warranty later and not.
_DIGITS = re.compile(r"\D")


def normalise_phone(value: str) -> str:
    digits = _DIGITS.sub("", value or "")
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) != 10 or digits[0] not in "6789":
        raise ValueError("Enter a valid 10-digit Indian mobile number")
    return f"+91{digits}"


PhoneStr = Annotated[str, Field(min_length=6, max_length=20)]


class Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PhoneMixin(BaseModel):
    @field_validator("phone", "customer_phone", mode="before", check_fields=False)
    @classmethod
    def _normalise(cls, v: str | None) -> str | None:
        return normalise_phone(v) if v else v


class Page(Base):
    total: int
    limit: int
    offset: int


class Ok(Base):
    ok: bool = True


__all__ = ["Base", "Ok", "Page", "PhoneMixin", "PhoneStr", "date", "datetime", "normalise_phone"]
