#  Copyright 2026 Canonical Ltd.
#  See LICENSE file for licensing details.

"""The unit tests for the  flask app."""

import json
import secrets
from typing import Callable, Iterator
from unittest.mock import MagicMock

import pytest
from flask import Flask
from flask.testing import FlaskClient
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

import webhook_router.app as app_module
import webhook_router.router
from tests.unit.helpers import create_correct_signature, create_incorrect_signature
from webhook_router.parse import Job, JobStatus, ParseError
from webhook_router.router import NonForwardableJobError, RoutingTable

TEST_PATH = "/webhook"
TEST_LABELS = ["self-hosted", "linux", "arm64"]
DEFAULT_SELF_HOSTED_LABELS = {"self-hosted", "linux"}


@pytest.fixture(name="flavours_yaml")
def flavours_yaml_fixture() -> str:
    """Create a flavours yaml file."""
    flavours_yaml = """
- small:
  - x64
  - small
- large:
    - arm64
    - large
"""
    return str(flavours_yaml)


@pytest.fixture(name="client")
def client_fixture(app: Flask) -> FlaskClient:
    """Create the flask test client."""
    return app.test_client()


@pytest.fixture(name="route_table")
def route_table_fixture() -> RoutingTable:
    """Create a route table."""
    return RoutingTable(
        value={
            ("arm64",): "large",
            ("large",): "large",
            ("arm64", "large"): "large",
            ("x64",): "small",
            ("small",): "small",
            ("small", "x64"): "small",
        },
        default_flavor="small",
    )


@pytest.fixture(name="router_mock")
def router_mock_fixture(monkeypatch: pytest.MonkeyPatch):
    """Mock the router function."""
    mock = MagicMock(spec=app_module.router)
    monkeypatch.setattr("webhook_router.app.router", mock)
    return mock


@pytest.fixture(name="app")
def app_fixture(
    flavours_yaml: str, route_table: RoutingTable, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Flask]:
    """Setup the flask app.

    Setup testing mode and add a stream handler to the logger.
    """
    mock = MagicMock(spec=webhook_router.router.to_routing_table, return_value=route_table)
    monkeypatch.setattr("webhook_router.app.to_routing_table", mock)
    app_module.app.config.update(
        {
            "TESTING": True,
            "FLAVOURS": flavours_yaml,
            "DEFAULT_SELF_HOSTED_LABELS": "self-hosted,linux",
            "DEFAULT_FLAVOUR": "small",
        }
    )
    app_module.config_app(app_module.app)
    yield app_module.app


@pytest.fixture(name="webhook_to_job_mock")
def webhook_to_job_mock_fixture(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock the webhook_to_job function."""
    mock = MagicMock(spec=app_module.webhook_to_job)
    monkeypatch.setattr("webhook_router.app.webhook_to_job", mock)
    return mock


def test_webhook_logs(
    client: FlaskClient,
    router_mock: MagicMock,
    route_table: RoutingTable,
):
    """
    arrange: A test client and a mocked forward function.
    act: Post a request to the webhook endpoint with a valid payload for the supported event.
    assert: 200 status code is returned and the expected job is forwarded.
    """
    data = _create_valid_data(JobStatus.QUEUED)
    expected_job = Job(
        labels=set(TEST_LABELS) - DEFAULT_SELF_HOSTED_LABELS,
        status=JobStatus.QUEUED,
        url=data["workflow_job"]["url"],
    )
    response = client.post(
        TEST_PATH,
        json=data,
        headers={app_module.GITHUB_EVENT_HEADER: app_module.SUPPORTED_GITHUB_EVENT},
    )
    assert response.status_code == 200
    router_mock.forward.assert_called_with(expected_job, routing_table=route_table)


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
    response = client.post(
        TEST_PATH,
        data="bad data",
        headers={app_module.GITHUB_EVENT_HEADER: app_module.SUPPORTED_GITHUB_EVENT},
    )
    assert response.status_code == UnsupportedMediaType.code

    response = client.post(
        TEST_PATH,
        data="bad data",
        content_type="application/json",
        headers={app_module.GITHUB_EVENT_HEADER: app_module.SUPPORTED_GITHUB_EVENT},
    )
    assert response.status_code == BadRequest.code


def test_wrong_github_event(client: FlaskClient):
    """
    arrange: A test client.
    act: Post a request to the webhook endpoint:
        1. with a missing GITHUB_EVENT_HEADER.
        2. with an unsupported GITHUB_EVENT_HEADER.
    assert: BadRequest status code is returned in both cases.
    """
    response = client.post(TEST_PATH, json={"test": "data"})
    assert response.status_code == BadRequest.code

    response = client.post(
        TEST_PATH, json={"test": "data"}, headers={app_module.GITHUB_EVENT_HEADER: "push"}
    )
    assert response.status_code == BadRequest.code


def test_invalid_payload(client: FlaskClient, webhook_to_job_mock: MagicMock):
    """
    arrange: A test client. Mock the webhook_to_job function to raise a ParseError.
    act: Post a request to the webhook endpoint with an invalid payload.
    assert: BadRequest status code is returned.
    """
    data = _create_valid_data(JobStatus.QUEUED)
    webhook_to_job_mock.side_effect = ParseError("Invalid payload")
    response = client.post(
        TEST_PATH,
        json=data,
        headers={app_module.GITHUB_EVENT_HEADER: app_module.SUPPORTED_GITHUB_EVENT},
    )
    assert response.status_code == BadRequest.code


def test_router_error(client: FlaskClient, router_mock: MagicMock):
    """
    arrange: A test client and a mocked labels_to_flavor function.
    act: Post a request to the webhook endpoint with a valid payload for the supported event.
    assert: 200 status code is returned and the logs contain the expected job and flavors.
    """
    router_mock.forward.side_effect = NonForwardableJobError("Invalid label combination")
    data = _create_valid_data(JobStatus.QUEUED)
    response = client.post(
        TEST_PATH,
        json=data,
        headers={app_module.GITHUB_EVENT_HEADER: app_module.SUPPORTED_GITHUB_EVENT},
    )
    assert response.status_code == 200
    assert "Not able to forward job" in response.data.decode("utf-8")


@pytest.mark.usefixtures("router_mock")
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
    app: Flask,
):
    """
    arrange: A test client and webhook secrets enabled.
    act: Post a request to the webhook endpoint.
    assert: Expected status code and reason.
    """
    secret = secrets.token_hex(16)
    payload_value = _create_valid_data("queued")
    payload = json.dumps(payload_value).encode("utf-8")
    app.config["WEBHOOK_SECRET"] = secret
    headers = {
        "Content-Type": "application/json",
        app_module.GITHUB_EVENT_HEADER: app_module.SUPPORTED_GITHUB_EVENT,
    }
    if create_signature_fct is not None:
        headers[app_module.WEBHOOK_SIGNATURE_HEADER] = create_signature_fct(secret, payload)

    response = client.post(TEST_PATH, data=payload, headers=headers)

    assert response.status_code == expected_status
    assert response.text == expected_reason


def test_health_check(client: FlaskClient, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: A test client. Mock router.can_forward to return True and False.
    act: Request the health check endpoint.
    assert: 200 status code is returned in the first case and 503 in the second.
    """
    monkeypatch.setattr(app_module.router, "can_forward", MagicMock(return_value=True))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.data == b""

    monkeypatch.setattr(app_module.router, "can_forward", MagicMock(return_value=False))
    response = client.get("/health")
    assert response.status_code == 503
    assert response.data == b"Router is not ready to forward jobs."


@pytest.mark.parametrize(
    "flavours_yaml, expected_err_msg",
    [
        pytest.param(
            "%s",
            "Invalid 'FLAVOURS' config. Invalid yaml.",
            id="invalid yaml",
        ),
        pytest.param(
            "",
            "FLAVOURS config is not set!",
            id="empty yaml",
        ),
        pytest.param(
            """
small:
    - x64
    - small
""",
            "Invalid 'FLAVOURS' config. Expected a YAML file with a list at the top level.",
            id="invalid format - no top level list",
        ),
        pytest.param(
            """
- small:
""",
            "Invalid 'FLAVOURS' config. Invalid format.",
            id="invalid format - flavour without labels",
        ),
        pytest.param(
            """
- small:
  - x64
  - small
- large:
    - arm64
    - large
- small:
    - arm64
    - small
""",
            "Invalid 'FLAVOURS' config. Duplicate flavour 'small' found.",
            id="duplicate flavour",
        ),
        pytest.param(
            """
- small:
  - x64:
        foobar
  - small
- large:
    - arm64
    - large
""",
            "Invalid 'FLAVOURS' config. Invalid format.",
            id="invalid format - label is a map",
        ),
        pytest.param(
            """
- small: [small]
  large: [large]
""",
            "Invalid 'FLAVOURS' config. Expected a single key-value pair: "
            "{'small': ['small'], 'large': ['large']}",
        ),
    ],
)
def test_invalid_app_config_flavours(flavours_yaml: str, expected_err_msg: str):
    """
    arrange: An invalid flavours yaml.
    act: Configure the app.
    assert: A ConfigError is raised with the expected error message.
    """
    app = Flask(__name__)
    app.config["FLAVOURS"] = flavours_yaml
    app.config["DEFAULT_SELF_HOSTED_LABELS"] = "self-hosted,linux"
    app.config["DEFAULT_FLAVOUR"] = "small"

    with pytest.raises(app_module.ConfigError) as exc_info:
        app_module.config_app(app)
    assert str(exc_info.value) == expected_err_msg


def test_invalid_app_config_default_self_hosted_labels_missing(flavours_yaml: str):
    """
    arrange: A valid flavours yaml and missing DEFAULT_SELF_HOSTED_LABELS.
    act: Configure the app.
    assert: A ConfigError is raised with the expected error message.
    """
    app = Flask(__name__)
    app.config["FLAVOURS"] = flavours_yaml
    app.config["DEFAULT_FLAVOUR"] = "small"

    with pytest.raises(app_module.ConfigError) as exc_info:
        app_module.config_app(app)
    assert str(exc_info.value) == "DEFAULT_SELF_HOSTED_LABELS config is not set!"


def test_invalid_app_config_default_flavour_missing(flavours_yaml: str):
    """
    arrange: A valid flavours yaml and missing DEFAULT_FLAVOUR.
    act: Configure the app.
    assert: A ConfigError is raised with the expected error message.
    """
    app = Flask(__name__)
    app.config["FLAVOURS"] = flavours_yaml
    app.config["DEFAULT_SELF_HOSTED_LABELS"] = "self-hosted,linux"

    with pytest.raises(app_module.ConfigError) as exc_info:
        app_module.config_app(app)
    assert str(exc_info.value) == "DEFAULT_FLAVOUR config is not set!"


def _create_valid_data(action: str) -> dict:
    """Create a valid payload for the supported event.

    Args:
        action: The action to include in the payload.

    Returns:
        A valid payload for the supported event.
    """
    return {
        "action": action,
        "workflow_job": {
            "id": 123456789,
            "run_id": 987654321,
            "status": "completed",
            "conclusion": "success",
            "labels": TEST_LABELS,
            "url": "https://api.github.com/repos/f/actions/jobs/8200803099",
        },
    }
