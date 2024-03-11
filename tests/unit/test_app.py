# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""The unit tests for the  flask app."""

import json
from pathlib import Path
from typing import Iterator

import pytest
from flask import Flask
from flask.testing import FlaskClient
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

from src.app import app as flask_app

TEST_PATH = "/webhook"


@pytest.fixture(name="webhook_logs")
def webhook_logs_fixture(tmp_path: Path):
    """Return a path for the webhook logs."""
    return tmp_path / "webhook.log"


@pytest.fixture(name="app")
def app_fixture(webhook_logs: Path) -> Iterator[Flask]:
    """Setup the flask app."""
    flask_app.config.update(
        {
            "TESTING": True,
        }
    )

    flask_app.config["WEBHOOK_FILE_PATH"] = webhook_logs

    yield flask_app


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
    response = client.post(TEST_PATH, json=data)
    assert response.status_code == 200
    assert webhook_logs.exists()
    assert webhook_logs.read_text() == f"{json.dumps(data)}\n"


def test_webhook_logs_get_appended(client: FlaskClient, webhook_logs: Path):
    """
    arrange: A test client and a webhook log file with existing logs.
    act: Post a request to the webhook endpoint.
    assert: the log file contains the payload and the existing logs.
    """
    webhook_logs.write_text("existing data\n")
    data = {"test": "data"}
    client.post(TEST_PATH, json=data)
    assert webhook_logs.exists()
    assert webhook_logs.read_text() == f"existing data\n{json.dumps(data)}\n"


def test_non_json_request(client: FlaskClient, webhook_logs: Path):
    """
    arrange: A test client and a webhook log file.
    act: Post a request to the webhook endpoint with
        1. non-json content.
        2. non-json content but with application/json content type.
    assert: the webhook log file does not exist and
        1. UnsupportedMediaType status code is returned.
        2. BadRequest status code is returned.
    """
    response = client.post(TEST_PATH, data="bad data")
    assert response.status_code == UnsupportedMediaType.code
    assert not webhook_logs.exists()

    response = client.post(TEST_PATH, data="bad data", content_type="application/json")
    assert response.status_code == BadRequest.code
    assert not webhook_logs.exists()
