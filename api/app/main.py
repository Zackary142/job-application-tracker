import os
import re
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from pydantic import BaseModel, Field

from app.extract import ExtractError, extract_job_ad
from app.models import Application, ApplicationIn
from app.repository import ApplicationRepository

app = FastAPI(title="Job Application Tracker API", version="1.0.0")

# frontend is on the cloudfront domain so need CORS. terraform sets ALLOWED_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ALLOWED_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache
def get_repo() -> ApplicationRepository:
    # cached so warm lambdas reuse the client
    return ApplicationRepository()


def get_user_id(request: Request) -> str:
    # api gateway checks the cognito token before lambda even runs, then passes
    # the claims through in the event. sub = the user's id in cognito
    event = request.scope.get("aws.event")
    if event:
        return event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
    # running locally (dev_server.py) - no api gateway, so fake a user
    if dev_user := os.environ.get("DEV_USER_ID"):
        return dev_user
    raise HTTPException(status_code=401, detail="Not logged in")


def can_autofill(request: Request) -> bool:
    # auto-fill costs money per go so it's only for accounts in the cognito
    # "autofill" group (added by hand in the console). anyone can sign up otherwise
    event = request.scope.get("aws.event")
    if event:
        claims = event["requestContext"]["authorizer"]["jwt"]["claims"]
        # http api passes lists through as a string like "[autofill admin]"
        return "autofill" in re.findall(r"[\w-]+", str(claims.get("cognito:groups", "")))
    return bool(os.environ.get("DEV_USER_ID"))


# tests override get_repo with a moto table and get_user_id with a header
Repo = Annotated[ApplicationRepository, Depends(get_repo)]
UserId = Annotated[str, Depends(get_user_id)]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/applications")
def list_applications(repo: Repo, user_id: UserId) -> list[Application]:
    return repo.list(user_id)


@app.post("/applications", status_code=status.HTTP_201_CREATED)
def create_application(data: ApplicationIn, repo: Repo, user_id: UserId) -> Application:
    return repo.create(user_id, data)


@app.get("/applications/{app_id}")
def get_application(app_id: str, repo: Repo, user_id: UserId) -> Application:
    found = repo.get(user_id, app_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return found


@app.put("/applications/{app_id}")
def replace_application(
    app_id: str, data: ApplicationIn, repo: Repo, user_id: UserId
) -> Application:
    updated = repo.replace(user_id, app_id, data)
    if updated is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return updated


@app.delete("/applications/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(app_id: str, repo: Repo, user_id: UserId) -> Response:
    if not repo.delete(user_id, app_id):
        raise HTTPException(status_code=404, detail="Application not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class JobAdText(BaseModel):
    # cap it so someone can't paste a novel in and run up the bill
    text: str = Field(min_length=20, max_length=20000)


@app.post("/extract")
def extract(
    data: JobAdText, user_id: UserId, allowed: Annotated[bool, Depends(can_autofill)]
) -> dict:
    # user_id isnt used, its just here so you have to be logged in
    if not allowed:
        raise HTTPException(status_code=403, detail="Auto-fill isn't turned on for your account")
    try:
        return extract_job_ad(data.text)
    except ExtractError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err


# lambda entrypoint
handler = Mangum(app)
