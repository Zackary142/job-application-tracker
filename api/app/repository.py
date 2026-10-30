# all the dynamo stuff lives here so the routes dont care about storage

import os
import uuid
from datetime import UTC, datetime

import boto3

from app.models import Application, ApplicationIn


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class ApplicationRepository:
    def __init__(self, table_name: str | None = None):
        table_name = table_name or os.environ["TABLE_NAME"]
        self.table = boto3.resource("dynamodb").Table(table_name)

    def list(self) -> list[Application]:
        # scan is fine for one user. if this ever had multiple users -> pk on user id + query
        items = []
        response = self.table.scan()
        items.extend(response["Items"])
        while "LastEvaluatedKey" in response:
            response = self.table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            items.extend(response["Items"])
        apps = [Application(**item) for item in items]
        return sorted(apps, key=lambda a: a.applied_on, reverse=True)

    def get(self, app_id: str) -> Application | None:
        item = self.table.get_item(Key={"id": app_id}).get("Item")
        return Application(**item) if item else None

    def create(self, data: ApplicationIn) -> Application:
        now = _now()
        app = Application(id=str(uuid.uuid4()), created_at=now, updated_at=now, **data.model_dump())
        self.table.put_item(Item=app.model_dump(mode="json"))
        return app

    def replace(self, app_id: str, data: ApplicationIn) -> Application | None:
        existing = self.get(app_id)
        if existing is None:
            return None
        app = Application(
            id=app_id, created_at=existing.created_at, updated_at=_now(), **data.model_dump()
        )
        self.table.put_item(Item=app.model_dump(mode="json"))
        return app

    def delete(self, app_id: str) -> bool:
        response = self.table.delete_item(Key={"id": app_id}, ReturnValues="ALL_OLD")
        return "Attributes" in response
