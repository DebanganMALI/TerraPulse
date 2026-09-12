from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Role


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=48)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    username: str
    role: Role
    display_name: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
