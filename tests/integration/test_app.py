#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration tests for the charmed flask application."""
import hashlib
import hmac
import json
import secrets
from typing import Optional, cast

import pytest
import requests
from juju.application import Application
from juju.model import Model
from pytest_operator.plugin import OpsTest

from webhook_router.app import WEBHOOK_SIGNATURE_HEADER

PORT = 8000


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
    headers = {"Content-Type": "application/json"}

    if webhook_secret:
        hash_object = hmac.new(
            webhook_secret.encode("utf-8"), msg=payload_bytes, digestmod=hashlib.sha256
        )
        signature = "sha256=" + hash_object.hexdigest()
        headers[WEBHOOK_SIGNATURE_HEADER] = signature

    return requests.post(f"{base_url}/webhook", data=payload_bytes, headers=headers, timeout=1)


async def _get_gunicorn_log(ops_test: OpsTest, unit_name: str) -> str:
    """Get the gunicorn log from the charm unit.

    Args:
        ops_test: The ops_test plugin.
        unit_name: The unit name.

    Returns:
        The gunicorn log.
    """
    ret, stdout, stderr = await ops_test.juju(
        "ssh", "--container", "flask-app", unit_name, "cat", "/var/log/flask/error.log"
    )

    assert ret == 0, f"Failed to retrieve gunicorn log, {stderr}"
    assert stdout is not None, "No output from gunicorn log"
    return stdout


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
async def test_receive_webhook(
    worker_count: int,
    ops_test: OpsTest,
    model: Model,
    app: Application,
    webhook_secret: Optional[str],
):
    """
    arrange: given a running charm with an amount of workers running the flask app
    act: call the webhook endpoint with worker_count payloads
    assert: successful requests and that the payloads are written to the gunicorn log
    """
    await app.set_config({"webhook-secret": webhook_secret})
    await model.wait_for_idle(apps=[app.name], status="active")

    payloads = [{f"test{i}": f"data{i}"} for i in range(worker_count)]

    unit = app.units[0]
    address = (await _get_unit_ips(ops_test=ops_test, application_name=app.name))[0]
    for payload in payloads:
        resp = _request(
            payload=payload, webhook_secret=webhook_secret, base_url=f"http://{address}:{PORT}"
        )
        assert resp.status_code == 200

    logs = await _get_gunicorn_log(ops_test=ops_test, unit_name=unit.name)

    for payload in payloads:
        assert json.dumps(payload) in logs
