import json
from pathlib import Path
from typing import Iterator

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import app


@pytest.fixture(name="webhook_logs")
def webhook_logs_fixture(tmp_path):
    """Create a fixture for the webhook logs."""
    return tmp_path / "webhook.log"


@pytest.fixture(name="app")
def app_fixture(webhook_logs: Path) -> Iterator[Flask]:
    """Setup the flask app."""
    app.config.update({
        "TESTING": True,
    })

    app.config["WEBHOOK_FILE_PATH"] = webhook_logs

    yield app


@pytest.fixture(name="client")
def client_fixture(app: Flask) -> FlaskClient:
    """Create the flask test client."""
    return app.test_client()


def test_webhook_logs(client: FlaskClient, webhook_logs: Path):
    """
    arrange: A test client and a webhook log file.
    act: Post a request to the webhook endpoint.
    assert: 200 status code is returned and the log file contains the payload of the request.
    """
    data = {"test": "data"}
    response = client.post("/webhook", json=data)
    assert response.status_code == 200
    assert webhook_logs.read_text() == f"{json.dumps(data)}\n"


def test_webhook_logs_get_appended(client: FlaskClient, webhook_logs: Path):
    """
    arrange: A test client and a webhook log file with existing logs.
    act: Post a request to the webhook endpoint.
    assert: 200 status code is returned and the log file contains the payload of the request.
    """
    webhook_logs.write_text("existing data\n")
    data = {"test": "data"}
    client.post("/webhook", json=data)
    assert webhook_logs.read_text() == f"existing data\n{json.dumps(data)}\n"
