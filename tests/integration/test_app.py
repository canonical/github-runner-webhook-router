#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration tests for the charmed flask application."""
import hashlib
import hmac
import itertools
import json
import random
import secrets
from typing import Optional, cast

import pytest
import requests
from juju.application import Application
from juju.model import Model
from juju.unit import Unit
from pytest_operator.plugin import OpsTest

from webhook_router.app import (
    GITHUB_EVENT_HEADER,
    SUPPORTED_GITHUB_EVENT,
    WEBHOOK_SIGNATURE_HEADER,
)
from webhook_router.webhook import Job, JobStatus

PORT = 8000


@pytest.mark.parametrize(
    "webhook_secret",
    [
        pytest.param(
            secrets.token_hex(16),
            id="with secret",
        ),
        pytest.param(
            "",
            id="without secret",
        ),
    ],
)
# using variables makes the test easier to read, but we need to disable pylint checks
async def test_forward_webhook(  # pylint: disable=too-many-locals
    ops_test: OpsTest,
    model: Model,
    app: Application,
    webhook_secret: Optional[str],
):
    """
    arrange: given a running charm and a particular flavour mapping
    act: call the webhook endpoint with several label combinations
    assert: the mq contains the expected jobs for the particular flavour mapping
    """
    flavours_yaml = """
- small: [small, x64, jammy]
- large: [large, x64, jammy]
- noble-large: [large, x64, noble]
- arm-large: [large, arm, jammy]
"""
    await app.set_config({"webhook-secret": webhook_secret, "flavours": flavours_yaml})
    await model.wait_for_idle(apps=[app.name], status="active")

    labels_by_flavour = {
        "small": [["small", "x64", "jammy"], ["small"], ["x64"], ["jammy"], []],
        "large": [["large", "x64", "jammy"], ["large"], ["x64", "large"], ["large", "jammy"]],
        "noble-large": [["noble", "large", "x64"], ["noble"], ["noble", "large"]],
        "arm-large": [["large", "arm", "jammy"], ["arm"], ["arm", "jammy"], ["arm", "large"]],
    }
    payloads_by_flavour = {
        flavour: [_create_valid_data(JobStatus.QUEUED, labels=labels) for labels in labels_list]
        for flavour, labels_list in labels_by_flavour.items()
    }

    address = (await _get_unit_ips(ops_test=ops_test, application_name=app.name))[0]
    for payload in itertools.chain(*payloads_by_flavour.values()):
        resp = _request(
            payload=payload, webhook_secret=webhook_secret, base_url=f"http://{address}:{PORT}"
        )
        assert resp.status_code == 200

    flavours = list(labels_by_flavour.keys())

    jobs_by_flavour = await _get_jobs_from_mq(
        ops_test=ops_test,
        unit=app.units[0],
        flavors=flavours,
    )

    expected_jobs_by_flavour = {
        flavour: [
            Job(
                status=payload["payload"]["action"],
                run_url=payload["payload"]["workflow_job"]["run_url"],
                labels=payload["payload"]["workflow_job"]["labels"],
            )
            for payload in payloads_by_flavour[flavour]
        ]
        for flavour in flavours
    }

    for flavour in flavours:
        actual_jobs = jobs_by_flavour.get(flavour, set())
        expected_jobs_for_flavour = expected_jobs_by_flavour[flavour]
        assert len(actual_jobs) == len(
            expected_jobs_for_flavour
        ), f"Expected: {expected_jobs_for_flavour}, Actual: {actual_jobs}"
        for job in expected_jobs_for_flavour:
            assert (
                job.json() in actual_jobs
            ), f"Expected: {expected_jobs_for_flavour}, Actual: {actual_jobs}"


async def test_receive_webhook_not_forwarded(ops_test: OpsTest, model: Model, app: Application):
    """
    arrange: given a running charm with a particular flavour mapping
    act: call the webhook endpoint with payloads with statuses that should not be forwarded
    assert: the mq does not contain any jobs
    """
    flavours_yaml = "- default: [default]"
    non_logged_statuses = [JobStatus.COMPLETED, JobStatus.IN_PROGRESS, JobStatus.WAITING]
    await app.set_config({"webhook-secret": "", "flavours": flavours_yaml})
    await model.wait_for_idle(apps=[app.name], status="active")

    payloads = [
        _create_valid_data(status, labels=["linux", "self-hosted", "default"])
        for status in non_logged_statuses
    ]

    address = (await _get_unit_ips(ops_test=ops_test, application_name=app.name))[0]
    for payload in payloads:
        # bandit thinks webhook_secret is a hardcoded password, ignore for the test
        resp = _request(
            payload=payload, webhook_secret="", base_url=f"http://{address}:{PORT}"
        )  # nosec
        assert resp.status_code == 200

    jobs_by_flavour = await _get_jobs_from_mq(
        ops_test=ops_test, unit=app.units[0], flavors=["default"]
    )

    assert not jobs_by_flavour.get("default")


async def test_receive_webhook_client_error(ops_test: OpsTest, model: Model, app: Application):
    """
    arrange: given a running charm with a particular flavour mapping
    act: call the webhook endpoint with an invalid payload or missing headers
        1. missing webhook signature header
        2. wrong signature
        3. missing X-Github-Event header
        4. invalid label combination
        5. invalid payload
    assert: the response status code is 403 for 1. + 2. and 400 for 3. + 4. + 5.
    """
    flavours_yaml = "- default: [default]"
    webhook_secret = secrets.token_hex(16)
    await app.set_config({"webhook-secret": webhook_secret, "flavours": flavours_yaml})
    await model.wait_for_idle(apps=[app.name], status="active")

    actual_payload = _create_valid_data("queued", labels=["linux", "self-hosted", "default"])
    payload_bytes = json.dumps(actual_payload).encode("utf-8")
    address = (await _get_unit_ips(ops_test=ops_test, application_name=app.name))[0]
    webhook_url = f"http://{address}:{PORT}/webhook"
    actual_signature = _create_signature(payload_bytes, webhook_secret)
    headers = {
        "Content-Type": "application/json",
        GITHUB_EVENT_HEADER: SUPPORTED_GITHUB_EVENT,
        WEBHOOK_SIGNATURE_HEADER: actual_signature,
    }
    # 1. Missing X-Github-Event header
    actual_headers = {k: v for k, v in headers.items() if k != WEBHOOK_SIGNATURE_HEADER}
    resp = requests.post(webhook_url, data=payload_bytes, headers=actual_headers, timeout=1)
    assert resp.status_code == 403

    # 2. Wrong signature
    actual_signature = actual_signature + "make it wrong"
    actual_headers = {
        "Content-Type": "application/json",
        "X-Github-Event": SUPPORTED_GITHUB_EVENT,
        WEBHOOK_SIGNATURE_HEADER: actual_signature,
    }
    resp = requests.post(webhook_url, data=payload_bytes, headers=actual_headers, timeout=1)
    assert resp.status_code == 403

    # 3. Missing X-Github-Event header
    actual_headers = {k: v for k, v in headers.items() if k != GITHUB_EVENT_HEADER}
    resp = requests.post(webhook_url, data=payload_bytes, headers=actual_headers, timeout=1)
    assert resp.status_code == 400

    # 4. invalid label combination
    actual_payload = _create_valid_data(
        "queued", labels=["linux", "self-hosted", "default", "invalid"]
    )
    actual_payload_bytes = json.dumps(actual_payload).encode("utf-8")
    actual_signature = _create_signature(actual_payload_bytes, webhook_secret)
    actual_headers = {
        "Content-Type": "application/json",
        GITHUB_EVENT_HEADER: SUPPORTED_GITHUB_EVENT,
        WEBHOOK_SIGNATURE_HEADER: actual_signature,
    }
    resp = requests.post(webhook_url, data=actual_payload_bytes, headers=actual_headers, timeout=1)
    assert resp.status_code == 400

    # 5. invalid payload
    actual_payload = {"event": "workflow_job", "payload": {"action": "queued"}}
    actual_payload_bytes = json.dumps(actual_payload).encode("utf-8")
    actual_signature = _create_signature(actual_payload_bytes, webhook_secret)
    actual_headers = {
        "Content-Type": "application/json",
        GITHUB_EVENT_HEADER: SUPPORTED_GITHUB_EVENT,
        WEBHOOK_SIGNATURE_HEADER: actual_signature,
    }
    resp = requests.post(webhook_url, data=actual_payload_bytes, headers=actual_headers, timeout=1)
    assert resp.status_code == 400


def _create_valid_data(action: str, labels: list[str]) -> dict:
    """Create a valid payload for the supported event.

    Args:
        action: The action to include in the payload.
        labels: The labels to include in the payload.

    Returns:
        A valid payload for the supported event.
    """
    # we are not using random.randint here for cryptographic purposes
    _id = random.randint(1, 10000)  # nosec
    return {
        "event": SUPPORTED_GITHUB_EVENT,
        "payload": {
            "action": action,
            "workflow_job": {
                "id": _id,
                "run_id": 987654321,
                "status": "completed",
                "conclusion": "success",
                "labels": labels,
                "run_url": f"https://api.github.com/repos/f/actions/runs/{_id}",
            },
        },
    }


def _create_signature(payload: bytes, secret: str) -> str:
    """Create a signature for the payload.

    Args:
        payload: The payload to sign.
        secret: The secret to sign the payload with.

    Returns:
        The signature.
    """
    hash_object = hmac.new(secret.encode("utf-8"), msg=payload, digestmod=hashlib.sha256)
    return "sha256=" + hash_object.hexdigest()


async def _get_unit_ips(ops_test: OpsTest, application_name: str) -> tuple[str, ...]:
    """Retrieve unit ip addresses of a certain application.

    Args:
        ops_test: ops_test plugin.
        application_name: application name.

    Returns:
        a tuple containing unit ip addresses.
    """
    _, status, _ = await ops_test.juju("status", "--format", "json")
    status = json.loads(status)
    units = status["applications"][application_name]["units"]
    return tuple(
        cast(str, unit_status["address"])
        for _, unit_status in sorted(units.items(), key=lambda kv: int(kv[0].split("/")[-1]))
    )


def _request(payload: dict, webhook_secret: Optional[str], base_url: str) -> requests.Response:
    """Send a request to the webhook endpoint.

    If webhook_secret is provided, the request is signed.

    Args:
        payload: The payload to send.
        webhook_secret: The webhook secret.
        base_url: The base url of the webhook endpoint.

    Returns:
        The response.
    """
    payload_bytes = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", GITHUB_EVENT_HEADER: SUPPORTED_GITHUB_EVENT}

    if webhook_secret:
        hash_object = hmac.new(
            webhook_secret.encode("utf-8"), msg=payload_bytes, digestmod=hashlib.sha256
        )
        signature = "sha256=" + hash_object.hexdigest()
        headers[WEBHOOK_SIGNATURE_HEADER] = signature

    return requests.post(f"{base_url}/webhook", data=payload_bytes, headers=headers, timeout=1)


async def _get_jobs_from_mq(ops_test: OpsTest, unit: Unit, flavors: list[str]) -> dict[str, set]:
    """Get the gunicorn log from the charm unit.

    Args:
        ops_test: The ops_test plugin.
        unit: The unit.
        flavors: The flavors to get the jobs from.

    Returns:
        The jobs by flavor retrieved from the mq.
    """
    mongodb_uri = await _get_mongodb_uri_from_integration_data(ops_test, unit)
    if not mongodb_uri:
        mongodb_uri = await _get_mongodb_uri_from_secrets(ops_test, unit.model)
    assert mongodb_uri, "mongodb uri not found in integration data or secret"

    # Accessing the queue is currently only supported from within the k8s cluster.
    # We workaround by writing a kombu script to the flask-app container and execute it there.
    kombu_script = f"""
import json
import sys
from kombu import Connection

mongodb_uri = "{mongodb_uri}"
flavors = {json.dumps(flavors)}

jobs_by_flavour = {{}}
with Connection(mongodb_uri) as conn:
    for flavor in flavors:
        jobs = []
        simple_queue = conn.SimpleQueue(flavor)

        for _ in range(simple_queue.qsize()):
            msg = simple_queue.get_nowait()
            jobs.append(msg.payload)
            msg.ack()
        jobs_by_flavour[flavor] = jobs
        simple_queue.close()

print(json.dumps(jobs_by_flavour))
"""
    code, _, stderr = await ops_test.juju(
        "ssh",
        "--container",
        "flask-app",
        unit.name,
        "echo",
        f"'{kombu_script}'",
        ">",
        "/kombu_script.py",
    )
    assert code == 0, f"Failed to write kombu script: {stderr}"
    code, stdout, stderr = await ops_test.juju(
        "ssh", "--container", "flask-app", unit.name, "python3", "/kombu_script.py"
    )
    assert code == 0, f"Failed to execute kombu script: {stderr}"
    return json.loads(stdout)


async def _get_mongodb_uri_from_integration_data(ops_test: OpsTest, unit: Unit) -> str | None:
    """Get the mongodb uri from the relation data.

    Args:
        ops_test: The ops_test plugin.
        unit: The juju unit containing the relation data.

    Returns:
        The mongodb uri or None if not found.
    """
    mongodb_uri = None
    _, unit_data, _ = await ops_test.juju("show-unit", unit.name, "--format", "json")
    unit_data = json.loads(unit_data)

    for rel_info in unit_data[unit.name]["relation-info"]:
        if rel_info["endpoint"] == "mongodb":
            try:
                mongodb_uri = rel_info["application-data"]["uris"]
                break
            except KeyError:
                pass

    return mongodb_uri


async def _get_mongodb_uri_from_secrets(ops_test, model: Model) -> str | None:
    """Get the mongodb uri from the secrets.

    Args:
        ops_test: The ops_test plugin.
        model: The juju model containing the unit.

    Returns:
        The mongodb uri or None if not found.
    """
    mongodb_uri = None

    juju_secrets = await model.list_secrets()
    for secret in juju_secrets["results"]:
        if secret.label == "database.2.user.secret":
            _, show_secret, _ = await ops_test.juju(
                "show-secret", secret.uri, "--reveal", "--format", "json"
            )
            show_secret = json.loads(show_secret)
            for value in show_secret.values():
                if "content" in value:
                    mongodb_uri = value["content"]["Data"]["uris"]
                    break
            if mongodb_uri:
                break
    return mongodb_uri
