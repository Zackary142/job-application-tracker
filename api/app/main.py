import os
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

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


# tests override get_repo with a moto table
Repo = Annotated[ApplicationRepository, Depends(get_repo)]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/applications")
def list_applications(repo: Repo) -> list[Application]:
    return repo.list()


@app.post("/applications", status_code=status.HTTP_201_CREATED)
def create_application(data: ApplicationIn, repo: Repo) -> Application:
    return repo.create(data)


@app.get("/applications/{app_id}")
def get_application(app_id: str, repo: Repo) -> Application:
    found = repo.get(app_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return found


@app.put("/applications/{app_id}")
def replace_application(app_id: str, data: ApplicationIn, repo: Repo) -> Application:
    updated = repo.replace(app_id, data)
    if updated is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return updated


@app.delete("/applications/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(app_id: str, repo: Repo) -> Response:
    if not repo.delete(app_id):
        raise HTTPException(status_code=404, detail="Application not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# lambda entrypoint
handler = Mangum(app)
