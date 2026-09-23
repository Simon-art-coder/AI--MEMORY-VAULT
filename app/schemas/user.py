"""
Pydantic schemas for user-facing data.

These are deliberately separate from app.models.user.User. The DB model
has a hashed_password column; that must never leave the server. Keeping
schemas and models separate means there's no risk of accidentally
returning a password hash in an API response.
"""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserRead(BaseModel):
    id: str
    email: EmailStr
    created_at: datetime

    # Lets Pydantic build this schema directly from a SQLAlchemy User
    # object (model_validate(user_instance)) instead of needing a dict.
    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
