"""Explicit API contracts, including strict rating and unknown-field validation."""

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=2, max_length=2000)
    session_id: uuid.UUID

    @field_validator("message")
    @classmethod
    def clean_message(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2 or any(ord(c) < 32 and c not in "\n\t\r" for c in value):
            raise ValueError("Enter a question with at least two characters and no control characters")
        return value


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: uuid.UUID
    value: StrictInt

    @field_validator("value")
    @classmethod
    def allowed_rating(cls, value: int) -> int:
        if value not in (-1, 1):
            raise ValueError("Rating must be -1 or 1")
        return value


class Source(BaseModel):
    id: str
    question: str
    score: float = Field(ge=0, le=1)


class ChatResponse(BaseModel):
    id: uuid.UUID
    answer: str
    intent: str
    confidence: float = Field(ge=0, le=1)
    mode: Literal["gemini", "retrieval", "no_match"]
    latency_ms: int = Field(ge=0)
    sources: list[Source]
    notice: str | None
    provider_error: str | None = None


class FAQ(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    category: Literal["Admissions", "Fees", "Academics", "Transport", "Support"]
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    keywords: str = Field(min_length=1)
