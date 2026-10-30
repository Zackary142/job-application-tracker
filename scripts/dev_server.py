# runs the api locally against a fake in-memory dynamo (moto), no aws account needed
# usage: pip install -r api/requirements-dev.txt uvicorn && python scripts/dev_server.py
import os
import sys
from pathlib import Path

import boto3
import uvicorn
from moto import mock_aws

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))
os.environ.setdefault("AWS_DEFAULT_REGION", "eu-west-2")
os.environ.setdefault("TABLE_NAME", "local-applications")

with mock_aws():
    boto3.client("dynamodb").create_table(
        TableName=os.environ["TABLE_NAME"],
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    from app.main import app

    uvicorn.run(app, port=8000)
