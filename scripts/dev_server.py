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
os.environ.setdefault("DEV_USER_ID", "local-dev")

with mock_aws():
    boto3.client("dynamodb").create_table(
        TableName=os.environ["TABLE_NAME"],
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
    import app.main as api

    # no bedrock locally, so auto-fill gives back a canned answer.
    # REAL_AI=1 to use the real thing (needs aws creds with bedrock access)
    if not os.environ.get("REAL_AI"):
        api.extract_job_ad = lambda text: {
            "company": "Acme",
            "role": "Junior Cloud Engineer",
            "salary": "£32,000 - £36,000 a year",
            "experience": "Some AWS or Azure, a degree or similar",
            "closes_on": "2026-11-30",
            "location": "London",
            "work_mode": "hybrid",
            "job_type": "Full-time, permanent",
            "skills": ["AWS", "Terraform", "Python", "CI/CD"],
        }

    uvicorn.run(api.app, port=8000)
