#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration tests for the flask app."""
import hashlib
import hmac
import json
import random
import secrets

# security considerations for subprocess are not relevant in this module
import subprocess  # nosec
from pathlib import Path
from time import sleep
from typing import Iterator, Optional

import pytest
import requests

from src.app import WEBHOOK_SIGNATURE_HEADER

BIND_HOST = "localhost"
BIND_PORT = 5000
BASE_URL = f"http://{BIND_HOST}:{BIND_PORT}"


@pytest.fixture(name="webhook_logs_dir")
def webhook_logs_dir_fixture(tmp_path: Path) -> Path:
    """Create a dir for the webhook logs."""
    logs_dir = tmp_path / "webhook_logs"
    logs_dir.mkdir()
    return logs_dir


@pytest.fixture(name="process_count")
def process_count_fixture() -> int:
    """Return the number of processes."""
    # We do not use randint for cryptographic purposes.
    return random.randint(2, 5)  # nosec


@pytest.fixture(
    name="webhook_secret",
    params=[pytest.param(True, id="with_secret"), pytest.param(False, id="without_secret")],
)
def webhook_secret_fixture(request) -> Optional[str]:
    """Return a webhook secret or None."""
    return secrets.token_hex(16) if request.param else None


@pytest.fixture(name="app")
def app_fixture(
    webhook_logs_dir: Path,
    process_count: int,
    webhook_secret: Optional[str],
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """Setup and run the flask app."""
    monkeypatch.setenv("WEBHOOK_LOGS_DIR", str(webhook_logs_dir))
    if webhook_secret:
        monkeypatch.setenv("WEBHOOK_SECRET", webhook_secret)

    # use subprocess to run the app using gunicorn with multiple workers
    command = f"gunicorn -w {process_count} --bind {BIND_HOST}:{BIND_PORT} src.app:app"

    with subprocess.Popen(command.split()) as p:  # nosec
        # It might take some time for the server to start
        for _ in range(10):
            try:
                requests.get(BASE_URL, timeout=1)
            except requests.exceptions.ConnectionError:
                print("Waiting for the app to start")
                sleep(1)
            else:
                break
        else:
            p.terminate()
            assert False, "The app did not start"

        yield
        p.terminate()


def _request(payload: dict, webhook_secret: Optional[str]) -> requests.Response:
    """Send a request to the webhook endpoint.

    If webhook_secret is provided, the request is signed.

    Args:
        payload: The payload to send.
        webhook_secret: The webhook secret.

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

    return requests.post(f"{BASE_URL}/webhook", data=payload_bytes, headers=headers, timeout=1)


@pytest.mark.usefixtures("app")
def test_receive_webhook(
    webhook_logs_dir: Path,
    process_count: int,
    webhook_secret: Optional[str],
):
    """
    arrange: given a running app with a process count and a webhook logs directory
    act: call the webhook endpoint with process_count payloads
    assert: the payloads are written to log files
    """
    for i in range(process_count):
        resp = _request(payload={f"test{i}": f"data{i}"}, webhook_secret=webhook_secret)
        assert resp.status_code == 200
    assert webhook_logs_dir.exists()
    log_files = list(webhook_logs_dir.glob("webhooks.*.log"))
    assert len(log_files) <= process_count
    log_files_content: set[str] = set()
    for log_file in log_files:
        log_files_content.update(filter(lambda s: s, log_file.read_text().split("\n")))
    assert log_files_content == {f'{{"test{i}": "data{i}"}}' for i in range(process_count)}
