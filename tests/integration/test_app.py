#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration tests for the flask app."""
import os
import random

# security considerations for subprocess are not relevant in this module
import subprocess  # nosec
from pathlib import Path
from time import sleep
from typing import Iterator

import pytest
import requests

BIND_HOST = "localhost"
BIND_PORT = 5000
BASE_URL = f"http://{BIND_HOST}:{BIND_PORT}"


@pytest.fixture(name="webhook_logs_dir", scope="module")
def webhook_logs_dir_fixture(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a dir for the webhook logs."""
    logs_dir = tmp_path_factory.mktemp("webhook_logs")
    return logs_dir


@pytest.fixture(name="process_count", scope="module")
def process_count_fixture() -> int:
    """Return the number of processes."""
    # We do not use randint for cryptographic purposes.
    return random.randint(2, 5)  # nosec


@pytest.fixture(name="app", scope="module", autouse=True)
def app_fixture(webhook_logs_dir: Path, process_count: int) -> Iterator[None]:
    """Setup and run the flask app."""
    os.environ["WEBHOOK_LOGS_DIR"] = str(webhook_logs_dir)

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


def test_receive_webhook(webhook_logs_dir: Path, process_count: int):
    """
    arrange: given a running app with a process count and a webhook logs directory
    act: call the webhook endpoint with process_count payloads
    assert: the payloads are written to log files
    """
    for i in range(process_count):
        resp = requests.post(f"{BASE_URL}/webhook", json={f"test{i}": f"data{i}"}, timeout=1)
        assert resp.status_code == 200
    assert webhook_logs_dir.exists()
    log_files = list(webhook_logs_dir.glob("webhooks.*.log"))
    assert len(log_files) <= process_count
    log_files_content: set[str] = set()
    for log_file in log_files:
        log_files_content.update(filter(lambda s: s, log_file.read_text().split("\n")))
    assert log_files_content == {f'{{"test{i}": "data{i}"}}' for i in range(process_count)}
