from __future__ import annotations  # <-- Add this line first

from sqlmodel import SQLModel, Field
from typing import Optional


class User(SQLModel, table=True):
    __tablename__ = "users"
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, nullable=False)
    phone_number: str = Field(unique=True, nullable=False)

    totp_secret: Optional[str] = Field(default=None)