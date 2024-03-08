#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Integration tests for the flask app."""

import os
import threading
from pathlib import Path

import pytest
import requests

import src.app as flask_app


@pytest.fixture(name="webhook_logs_dir", scope="module")
def webhook_logs_dir_fixture(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a dir for the webhook logs."""
    logs_dir = tmp_path_factory.mktemp("webhook_logs")
    return logs_dir


@pytest.fixture(name="app", scope="module", autouse=True)
def app_fixture(webhook_logs_dir: Path):
    """Setup and run the flask app."""
    os.environ["WEBHOOK_LOGS_DIR"] = str(webhook_logs_dir)
    flask_app.setup_webhook_log_file()
    thread = threading.Thread(target=flask_app.app.run, args=("localhost", 5000), daemon=True)
    thread.start()


def test_receive_webhook(webhook_logs_dir: Path):
    """
    arrange: given a running app and a webhook logs directory
    act: call the webhook endpoint with a payload
    assert: the payload is written to a log file
    """
    resp = requests.post("http://localhost:5000/webhook", json={"test": "data"}, timeout=5)
    assert resp.status_code == 200
    resp = requests.post("http://localhost:5000/webhook", json={"test2": "data2"}, timeout=5)
    assert resp.status_code == 200
    assert webhook_logs_dir.exists()
    log_files = list(webhook_logs_dir.glob("webhooks.*.log"))
    assert len(log_files) == 1
    log_file = log_files[0]
    assert log_file.read_text() == '{"test": "data"}\n{"test2": "data2"}\n'
