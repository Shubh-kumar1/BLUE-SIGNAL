from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    email: EmailStr
    password: str = Field(min_length=6, max_length=1024)
    role: str = "citizen"
    full_name: str = ""
    authority_registration_token: str | None = None


class CitizenPostRequest(BaseModel):
    title: str = Field(default="Flood Report", min_length=1, max_length=256)
    description: str = Field(default="", max_length=10_000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    location_name: str = Field(default="Unknown Location", max_length=256)
    media_url: str | None = None


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class VoteRequest(BaseModel):
    vote_type: str


class TextClassificationRequest(BaseModel):
    text: str = Field(min_length=1)


class ImageClassificationRequest(BaseModel):
    image_path: str


class AuthUser(BaseModel):
    id: int
    username: str
    role: str
    full_name: str | None


class LoginResponse(BaseModel):
    token: str
    user: AuthUser


class MessageResponse(BaseModel):
    message: str
