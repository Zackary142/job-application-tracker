from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl


class Status(StrEnum):
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class WorkMode(StrEnum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"


class ApplicationIn(BaseModel):
    # what the frontend sends on create/update
    company: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=100)
    status: Status = Status.APPLIED
    applied_on: date
    url: HttpUrl | None = None
    notes: str = Field(default="", max_length=2000)
    # these are optional, mostly filled in by the job ad auto-fill.
    # old items in dynamo dont have them so they need defaults
    salary: str = Field(default="", max_length=200)
    experience: str = Field(default="", max_length=300)
    closes_on: date | None = None
    location: str = Field(default="", max_length=100)
    work_mode: WorkMode | None = None
    job_type: str = Field(default="", max_length=100)
    skills: list[str] = Field(default_factory=list, max_length=20)


class Application(ApplicationIn):
    id: str
    created_at: str
    updated_at: str
