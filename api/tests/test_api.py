# moto fakes dynamo so these run without aws creds

import boto3
import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from moto import mock_aws

from app.main import app, can_autofill, get_repo, get_user_id
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
        app.dependency_overrides[can_autofill] = lambda: True
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


# --- job ad auto-fill. bedrock is faked, these check our side of it ---

AD = "Junior Cloud Engineer at Acme. £32k-£36k. Hybrid, London. Closes 30 Nov 2026."


class FakeMessages:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, **kwargs):
        self.messages = FakeMessages(**kwargs)


def fake_response(stop_reason="end_turn", **overrides):
    from types import SimpleNamespace

    from app.extract import JobAd

    fields = {
        "company": "Acme",
        "role": "Junior Cloud Engineer",
        "salary": "£32,000 - £36,000 a year",
        "experience": "Some AWS experience",
        "closes_on": "2026-11-30",
        "location": "London",
        "work_mode": "hybrid",
        "job_type": "Full-time, permanent",
        "skills": ["AWS", "Terraform"],
        **overrides,
    }
    return SimpleNamespace(stop_reason=stop_reason, parsed_output=JobAd(**fields))


@pytest.fixture
def fake_ai(monkeypatch):
    def use(**kwargs):
        fake = FakeClient(**kwargs)
        monkeypatch.setattr("app.extract.get_client", lambda: fake)
        return fake

    return use


def test_extract_fills_fields(client, fake_ai):
    fake = fake_ai(response=fake_response())
    res = client.post("/extract", json={"text": AD})
    assert res.status_code == 200
    body = res.json()
    assert body["salary"] == "£32,000 - £36,000 a year"
    assert body["closes_on"] == "2026-11-30"
    assert body["work_mode"] == "hybrid"
    # the ad goes in the user message, wrapped in tags
    sent = fake.messages.calls[0]
    assert AD in sent["messages"][0]["content"]
    assert "anthropic.claude" in sent["model"]


def test_extract_result_can_be_saved(client, fake_ai):
    fake_ai(response=fake_response())
    fields = client.post("/extract", json={"text": AD}).json()
    saved = client.post("/applications", json={**SAMPLE, **fields})
    assert saved.status_code == 201
    assert saved.json()["skills"] == ["AWS", "Terraform"]


def test_extract_drops_bad_dates(client, fake_ai):
    fake_ai(response=fake_response(closes_on="end of the month"))
    assert client.post("/extract", json={"text": AD}).json()["closes_on"] is None


def test_extract_refusal(client, fake_ai):
    fake_ai(response=fake_response(stop_reason="refusal"))
    res = client.post("/extract", json={"text": AD})
    assert res.status_code == 502
    assert "Couldn't read" in res.json()["detail"]


def test_extract_bedrock_down(client, fake_ai):
    import anthropic
    import httpx2

    req = httpx2.Request("POST", "https://bedrock-mantle.eu-west-2.api.aws/anthropic/v1/messages")
    fake_ai(error=anthropic.APIConnectionError(request=req))
    res = client.post("/extract", json={"text": AD})
    assert res.status_code == 502


def test_extract_needs_login(client):
    app.dependency_overrides.pop(get_user_id)
    assert client.post("/extract", json={"text": AD}).status_code == 401


def test_extract_text_limits(client):
    assert client.post("/extract", json={"text": "too short"}).status_code == 422
    assert client.post("/extract", json={"text": "x" * 20001}).status_code == 422


def test_old_items_without_new_fields_still_load(client):
    # items saved before the auto-fill fields existed
    boto3.resource("dynamodb").Table(TABLE).put_item(
        Item={
            "user_id": "alice",
            "id": "old",
            "created_at": "x",
            "updated_at": "x",
            **SAMPLE,
            "status": "applied",
            "notes": "",
        }
    )
    body = client.get("/applications/old").json()
    assert body["salary"] == "" and body["closes_on"] is None and body["skills"] == []


def test_extract_only_for_autofill_group(client):
    app.dependency_overrides[can_autofill] = lambda: False
    res = client.post("/extract", json={"text": AD})
    assert res.status_code == 403


@pytest.mark.parametrize(
    ("groups", "allowed"),
    [("[autofill]", True), ("[admin autofill]", True), ("[other]", False), (None, False)],
)
def test_autofill_group_from_token(groups, allowed):
    from types import SimpleNamespace

    claims = {"sub": "abc"} if groups is None else {"sub": "abc", "cognito:groups": groups}
    event = {"requestContext": {"authorizer": {"jwt": {"claims": claims}}}}
    assert can_autofill(SimpleNamespace(scope={"aws.event": event})) is allowed


# --- pasting a link instead of the ad ---

JOB_URL = "https://jobs.example.com/cloud-engineer"


def test_extract_from_link(client, fake_ai, monkeypatch):
    fake = fake_ai(response=fake_response())
    monkeypatch.setattr("app.main.fetch_page_text", lambda url: "page text " + AD)
    res = client.post("/extract", json={"text": f"  {JOB_URL}\n"})
    assert res.status_code == 200
    assert res.json()["url"] == JOB_URL  # fills in the job url field too
    assert "page text" in fake.messages.calls[0]["messages"][0]["content"]


def test_extract_link_that_wont_open(client, fake_ai, monkeypatch):
    from app.fetch_page import PageError

    fake = fake_ai(response=fake_response())

    def blocked(url):
        raise PageError("Couldn't open that link")

    monkeypatch.setattr("app.main.fetch_page_text", blocked)
    res = client.post("/extract", json={"text": JOB_URL})
    assert res.status_code == 422
    assert fake.messages.calls == []  # didnt waste a model call


def test_ad_text_with_a_link_inside_isnt_treated_as_a_link(client, fake_ai, monkeypatch):
    fake_ai(response=fake_response())
    monkeypatch.setattr("app.main.fetch_page_text", lambda url: pytest.fail("shouldnt fetch"))
    res = client.post("/extract", json={"text": f"{AD} apply at {JOB_URL}"})
    assert res.status_code == 200
    assert "url" not in res.json()
