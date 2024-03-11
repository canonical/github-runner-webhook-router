# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Flask application which receives GitHub webhooks and logs those."""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from flask import Flask, request

app = Flask(__name__)
app.config.from_prefixed_env()


def _log_file_name() -> str:
    """Create the log file name.

    Returns:
        The log file name.
    """
    # We use the process ID to avoid race conditions between multiple instances of the app.
    pid = os.getpid()
    return f"webhooks.{pid}.log"


def _setup_webhook_log_file() -> None:
    """Set the log file path."""
    webhook_logs_dir = Path(os.environ.get("WEBHOOK_LOGS_DIR", "/var/log/whrouter"))
    app.config["WEBHOOK_FILE_PATH"] = webhook_logs_dir / _log_file_name()


def setup_config() -> None:
    """Load and set the config."""
    app.config.from_prefixed_env()
    _setup_webhook_log_file()


setup_config()


def _write_webhook_log(payload: Any) -> None:
    """Append the webhook payload to a file.

    Args:
        payload: The payload to write.
    """
    with app.config["WEBHOOK_FILE_PATH"].open("a") as f:
        json.dump(payload, f)
        f.write("\n")


@app.route("/webhook", methods=["POST"])
def handle_github_webhook() -> tuple[str, int]:
    """Receive a GitHub webhook and append the payload to a file.

    Returns:
        A tuple containing an empty string and 200 status code.
    """
    payload = request.get_json()
    app.logger.debug("Received webhook: %s", payload)
    _write_webhook_log(payload)
    return "", 200


if __name__ == "__main__":
    # Start development server
    app.logger.addHandler(logging.StreamHandler(sys.stdout))
    app.logger.setLevel(logging.DEBUG)
    app.run()
