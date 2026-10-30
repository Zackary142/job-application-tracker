from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl


class Status(StrEnum):
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class ApplicationIn(BaseModel):
    # what the frontend sends on create/update
    company: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=100)
    status: Status = Status.APPLIED
    applied_on: date
    url: HttpUrl | None = None
    notes: str = Field(default="", max_length=2000)


class Application(ApplicationIn):
    id: str
    created_at: str
    updated_at: str
