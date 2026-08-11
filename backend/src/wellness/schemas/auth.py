import re
from datetime import date

from pydantic import BaseModel, field_validator

# Deliberately not pydantic.EmailStr: that needs the email-validator extra,
# which isn't a project dependency. A simple shape check is enough here —
# real deliverability is only ever proven by someone completing signup.
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

MIN_AGE_YEARS = 13


class RegisterRequest(BaseModel):
    """POST /api/v1/auth/register. Distinct from UserCreate (schemas/users.py):
    this is the real signup entry point and carries validation UserCreate
    intentionally doesn't (see the note there and in api/v1/users.py) —
    email shape, and a minimum age, since this app collects biometric data
    from whoever signs up.

    password's minimum length is deliberately NOT a Field constraint here —
    see api/v1/auth.py for why it's checked in the endpoint body instead.
    """

    full_name: str
    email: str
    password: str
    date_of_birth: date
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    country: str | None = None
    timezone: str = "Asia/Beirut"
    currency: str = "LBP"

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        value = value.strip()
        if not _EMAIL_RE.match(value):
            raise ValueError("Enter a valid email")
        return value

    @field_validator("date_of_birth")
    @classmethod
    def _validate_age(cls, value: date) -> date:
        today = date.today()
        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        if age < MIN_AGE_YEARS:
            raise ValueError(f"Must be at least {MIN_AGE_YEARS} years old")
        return value


class LoginRequest(BaseModel):
    """POST /api/v1/auth/login. Deliberately unvalidated beyond "these are
    strings": this is a credential check, not a data-quality gate, and
    rejecting malformed input here before the rate limit / password check
    would just be one more way to fail differently for different inputs.
    """

    email: str
    password: str


class AccessTokenResponse(BaseModel):
    """Response body for login and refresh. The refresh token never appears
    here — it's httpOnly-cookie-only, see api/v1/auth.py.
    """

    access_token: str
    token_type: str = "bearer"
