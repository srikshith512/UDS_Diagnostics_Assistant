"""Request models. Validation lives here so the routes stay thin."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Fault = Optional[Literal["skip_security"]]


class Bench(BaseModel):
    session: int = Field(1, description="Active diagnostic session (1 or 3)")
    unlocked: bool = False
    seed_issued: bool = False
    fault: Fault = None


class ValidateIn(Bench):
    request_hex: str = Field(..., max_length=20000)


class QuestionIn(BaseModel):
    question: str = Field(..., min_length=2, max_length=500)


class AssistIn(Bench):
    description: str = Field(..., min_length=3, max_length=500)


class ManualTestIn(Bench):
    request_hex: str = Field(..., max_length=20000)
    title: Optional[str] = Field(None, max_length=120)


class ReviewIn(BaseModel):
    status: Literal["Draft", "Approved", "Rejected"]
    comment: str = Field("", max_length=500)


class RunIn(BaseModel):
    fault: Fault = None
