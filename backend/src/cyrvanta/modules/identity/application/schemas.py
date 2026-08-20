from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    tenant_slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,63}$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)
    remember_me: bool = False


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=32)


class LogoutRequest(RefreshRequest):
    pass


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    remember_me: bool = False


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CurrentUserRole(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    name: str


class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    email: EmailStr
    display_name: str
    # What the signed-in person is allowed to be, in their own words. Without
    # it the interface can offer an action and refuse it a moment later with no
    # explanation the user could have anticipated -- and once authorization
    # depends on which hat someone is wearing, they need to know which hat that
    # is before they act.
    roles: list[CurrentUserRole] = []
