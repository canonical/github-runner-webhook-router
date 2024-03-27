# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""The unit tests for the  flask app."""

import json
import secrets
from pathlib import Path
from typing import Callable, Iterator

import pytest
from flask import Flask
from flask.testing import FlaskClient
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

import src.app as app_module
from tests.unit.helpers import create_correct_signature, create_incorrect_signature

TEST_PATH = "/webhook"


@pytest.fixture(name="webhook_logs")
def webhook_logs_fixture(tmp_path: Path):
    """Return a path for the webhook logs."""
    return tmp_path / "webhook.log"


@pytest.fixture(name="app")
def app_fixture(webhook_logs: Path) -> Iterator[Flask]:
    """Setup the flask app."""
    app_module.app.config.update(
        {
            "TESTING": True,
        }
    )

    app_module.setup_logger(log_file=webhook_logs)

    yield app_module.app


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


@pytest.mark.parametrize(
    "create_signature_fct, expected_status, expected_reason",
    [
        pytest.param(
            create_correct_signature,
            200,
            "",
            id="correct signature",
        ),
        pytest.param(
            create_incorrect_signature,
            403,
            "Signature validation failed!",
            id="incorrect signature",
        ),
        pytest.param(None, 403, "X-Hub-signature-256 header is missing!", id="missing signature"),
    ],
)
def test_webhook_validation(
    client: FlaskClient,
    create_signature_fct: Callable[[str, bytes], str],
    expected_status: int,
    expected_reason: str,
):
    """
    arrange: A test client and webhook secrets enabled.
    act: Post a request to the webhook endpoint.
    assert: Expected status code and reason.
    """
    secret = secrets.token_hex(16)
    payload_value = secrets.token_hex(16)
    payload = json.dumps({"value": payload_value}).encode("utf-8")

    app_module.app.config["WEBHOOK_SECRET"] = secret
    headers = {"Content-Type": "application/json"}
    if create_signature_fct is not None:
        headers[app_module.WEBHOOK_SIGNATURE_HEADER] = create_signature_fct(secret, payload)
    response = client.post(TEST_PATH, data=payload, headers=headers)
    assert response.status_code == expected_status
    assert response.text == expected_reason
