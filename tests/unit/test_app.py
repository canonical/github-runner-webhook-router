# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""The unit tests for the  flask app."""

import json
import logging
import secrets
import sys
from typing import Callable, Iterator

import pytest
from flask import Flask
from flask.testing import FlaskClient
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

import webhook_router.app as app_module
from tests.unit.helpers import create_correct_signature, create_incorrect_signature

TEST_PATH = "/webhook"


@pytest.fixture(name="app")
def app_fixture() -> Iterator[Flask]:
    """Setup the flask app.

    Setup testing mode and add a stream handler to the logger.
    """
    app_module.app.config.update(
        {
            "TESTING": True,
        }
    )

    app_module.app.logger.addHandler(logging.StreamHandler(sys.stdout))
    app_module.app.logger.setLevel(logging.DEBUG)

    yield app_module.app


@pytest.fixture(name="client")
def client_fixture(app: Flask) -> FlaskClient:
    """Create the flask test client."""
    return app.test_client()


def test_webhook_logs(client: FlaskClient, caplog: pytest.LogCaptureFixture):
    """
    arrange: A test client and a webhook log file.
    act: Post a request to the webhook endpoint.
    assert: 200 status code is returned and the logs contain the payload of the request.
    """
    data = {"test": "data"}
    response = client.post(TEST_PATH, json=data)
    assert response.status_code == 200
    assert json.dumps(data) in caplog.text


def test_non_json_request(client: FlaskClient):
    """
    arrange: A test client and a webhook log file.
    act: Post a request to the webhook endpoint with
        1. non-json content.
        2. non-json content but with application/json content type.
    assert:
        1. UnsupportedMediaType status code is returned.
        2. BadRequest status code is returned.
    """
    response = client.post(TEST_PATH, data="bad data")
    assert response.status_code == UnsupportedMediaType.code

    response = client.post(TEST_PATH, data="bad data", content_type="application/json")
    assert response.status_code == BadRequest.code


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
    monkeypatch: pytest.MonkeyPatch,
):
    """
    arrange: A test client and webhook secrets enabled.
    act: Post a request to the webhook endpoint.
    assert: Expected status code and reason.
    """
    secret = secrets.token_hex(16)
    payload_value = secrets.token_hex(16)
    payload = json.dumps({"value": payload_value}).encode("utf-8")
    monkeypatch.setenv("FLASK_WEBHOOK_SECRET", secret)
    headers = {"Content-Type": "application/json"}
    if create_signature_fct is not None:
        headers[app_module.WEBHOOK_SIGNATURE_HEADER] = create_signature_fct(secret, payload)

    response = client.post(TEST_PATH, data=payload, headers=headers)

    assert response.status_code == expected_status
    assert response.text == expected_reason
