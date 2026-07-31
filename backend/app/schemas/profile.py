"""Shared broker-profile field types.

Sign-in (`/auth/otp/request`) and profile edit (`PATCH /me`) collect the same
fields, so the validation lives here once and both import it.
"""

from datetime import date
from typing import Annotated, Literal

from pydantic import AfterValidator, Field

PINCODE_PATTERN = r"^\d{6}$"  # India

# GB Rewards is declared 18+ on Google Play (authorised channel partners only),
# so the floor is enforced server-side rather than trusted from the client.
MIN_AGE_YEARS = 18
MAX_AGE_YEARS = 120

Gender = Literal["male", "female"]


def _validate_dob(value: date) -> date:
    today = date.today()
    if value > today:
        raise ValueError("Date of birth cannot be in the future")
    # Whole years elapsed; the tuple compare handles birthdays later this year.
    age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
    if age < MIN_AGE_YEARS:
        raise ValueError(f"You must be at least {MIN_AGE_YEARS} years old to join")
    if age > MAX_AGE_YEARS:
        raise ValueError("Date of birth is not valid")
    return value


Dob = Annotated[date, AfterValidator(_validate_dob)]
AddressLine = Annotated[str, Field(min_length=1, max_length=500)]
City = Annotated[str, Field(min_length=1, max_length=120)]
State = Annotated[str, Field(min_length=1, max_length=120)]
Pincode = Annotated[str, Field(pattern=PINCODE_PATTERN)]
