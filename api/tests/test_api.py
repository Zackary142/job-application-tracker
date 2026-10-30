# moto fakes dynamo so these run without aws creds

import boto3
import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from moto import mock_aws

from app.main import app, get_repo, get_user_id
from app.repository import ApplicationRepository

TABLE = "test-applications"
SAMPLE = {"company": "Acme", "role": "Junior DevOps Engineer", "applied_on": "2026-10-01"}


def fake_user(request: Request) -> str:
    # pretend to be whoever's in the X-Test-User header (default alice)
    return request.headers.get("X-Test-User", "alice")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-2")
    with mock_aws():
        boto3.client("dynamodb").create_table(
            TableName=TABLE,
            KeySchema=[
                {"AttributeName": "user_id", "KeyType": "HASH"},
                {"AttributeName": "id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        app.dependency_overrides[get_repo] = lambda: ApplicationRepository(TABLE)
        app.dependency_overrides[get_user_id] = fake_user
        yield TestClient(app)
        app.dependency_overrides.clear()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_create_and_get(client):
    created = client.post("/applications", json=SAMPLE)
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "applied"
    assert client.get(f"/applications/{body['id']}").json() == body


def test_list_is_newest_first(client):
    client.post("/applications", json={**SAMPLE, "applied_on": "2026-09-01"})
    client.post("/applications", json={**SAMPLE, "applied_on": "2026-10-15"})
    dates = [a["applied_on"] for a in client.get("/applications").json()]
    assert dates == ["2026-10-15", "2026-09-01"]


def test_replace_keeps_created_at(client):
    created = client.post("/applications", json=SAMPLE).json()
    updated = client.put(
        f"/applications/{created['id']}", json={**SAMPLE, "status": "interviewing"}
    ).json()
    assert updated["status"] == "interviewing"
    assert updated["created_at"] == created["created_at"]


def test_delete(client):
    created = client.post("/applications", json=SAMPLE).json()
    assert client.delete(f"/applications/{created['id']}").status_code == 204
    assert client.get(f"/applications/{created['id']}").status_code == 404


def test_missing_returns_404(client):
    assert client.get("/applications/nope").status_code == 404
    assert client.put("/applications/nope", json=SAMPLE).status_code == 404
    assert client.delete("/applications/nope").status_code == 404


@pytest.mark.parametrize(
    "bad",
    [
        {**SAMPLE, "company": ""},
        {**SAMPLE, "status": "ghosted"},
        {**SAMPLE, "applied_on": "not-a-date"},
        {"company": "Acme"},
    ],
)
def test_validation(client, bad):
    assert client.post("/applications", json=bad).status_code == 422


def test_users_cant_see_each_others_data(client):
    mine = client.post("/applications", json=SAMPLE).json()
    bob = {"X-Test-User": "bob"}
    assert client.get("/applications", headers=bob).json() == []
    assert client.get(f"/applications/{mine['id']}", headers=bob).status_code == 404
    assert client.put(f"/applications/{mine['id']}", json=SAMPLE, headers=bob).status_code == 404
    assert client.delete(f"/applications/{mine['id']}", headers=bob).status_code == 404
    # still there for alice
    assert client.get(f"/applications/{mine['id']}").status_code == 200


def test_no_user_is_401(client, monkeypatch):
    app.dependency_overrides.pop(get_user_id)
    monkeypatch.delenv("DEV_USER_ID", raising=False)
    assert client.get("/applications").status_code == 401
    assert client.get("/health").status_code == 200


def test_user_id_comes_from_the_cognito_claims():
    event = {"requestContext": {"authorizer": {"jwt": {"claims": {"sub": "user-123"}}}}}
    request = Request({"type": "http", "aws.event": event})
    assert get_user_id(request) == "user-123"
