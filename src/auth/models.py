import re
from pydantic import BaseModel, Field, field_validator


_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    email: str
    password: str = Field(min_length=8, max_length=128)
    verification_code: str = Field(min_length=6, max_length=6)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if not _EMAIL_REGEX.match(v):
            raise ValueError("邮箱格式无效")
        return v.lower()


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if not _EMAIL_REGEX.match(v):
            raise ValueError("邮箱格式无效")
        return v.lower()


class RefreshRequest(BaseModel):
    refresh_token: str


class SendVerificationCodeRequest(BaseModel):
    email: str
    turnstile_token: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if not _EMAIL_REGEX.match(v):
            raise ValueError("邮箱格式无效")
        return v.lower()


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    created_at: str


class ErrorResponse(BaseModel):
    detail: str

class GeoResponse(BaseModel):
    ip: str
    country: str | None = None
    city: str | None = None
    region: str | None = None
    latitude: str | None = None
    longitude: str | None = None
    timezone: str | None = None


class SetPasswordRequest(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class OAuthAccountInfo(BaseModel):
    provider: str
    provider_user_id: str
    provider_email: str | None = None
    provider_name: str | None = None
    provider_avatar_url: str | None = None
    created_at: str


class UserDetailResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    created_at: str
    has_password: bool
    oauth_accounts: list[OAuthAccountInfo]


class LoginHistoryRecord(BaseModel):
    id: str
    action: str
    method: str | None = None
    ip: str | None = None
    country: str | None = None
    city: str | None = None
    region: str | None = None
    user_agent: str | None = None
    created_at: str


class LoginHistoryResponse(BaseModel):
    records: list[LoginHistoryRecord]
    total: int
    page: int
    page_size: int
