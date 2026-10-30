# all the dynamo stuff lives here so the routes dont care about storage

import os
import uuid
from datetime import UTC, datetime

import boto3
from boto3.dynamodb.conditions import Key

from app.models import Application, ApplicationIn


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class ApplicationRepository:
    def __init__(self, table_name: str | None = None):
        table_name = table_name or os.environ["TABLE_NAME"]
        self.table = boto3.resource("dynamodb").Table(table_name)

    # table key is (user_id, id) so every call is scoped to one user -
    # you can't read or touch someone else's items even with their id

    def list(self, user_id: str) -> list[Application]:
        items = []
        kwargs = {"KeyConditionExpression": Key("user_id").eq(user_id)}
        while True:
            response = self.table.query(**kwargs)
            items.extend(response["Items"])
            if "LastEvaluatedKey" not in response:
                break
            kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
        apps = [Application(**item) for item in items]
        return sorted(apps, key=lambda a: a.applied_on, reverse=True)

    def get(self, user_id: str, app_id: str) -> Application | None:
        item = self.table.get_item(Key={"user_id": user_id, "id": app_id}).get("Item")
        return Application(**item) if item else None

    def create(self, user_id: str, data: ApplicationIn) -> Application:
        now = _now()
        app = Application(id=str(uuid.uuid4()), created_at=now, updated_at=now, **data.model_dump())
        self._put(user_id, app)
        return app

    def replace(self, user_id: str, app_id: str, data: ApplicationIn) -> Application | None:
        existing = self.get(user_id, app_id)
        if existing is None:
            return None
        app = Application(
            id=app_id, created_at=existing.created_at, updated_at=_now(), **data.model_dump()
        )
        self._put(user_id, app)
        return app

    def delete(self, user_id: str, app_id: str) -> bool:
        response = self.table.delete_item(
            Key={"user_id": user_id, "id": app_id}, ReturnValues="ALL_OLD"
        )
        # .get not "in" - some versions hand back an empty dict for a missing item
        return bool(response.get("Attributes"))

    def _put(self, user_id: str, app: Application) -> None:
        self.table.put_item(Item={"user_id": user_id, **app.model_dump(mode="json")})
