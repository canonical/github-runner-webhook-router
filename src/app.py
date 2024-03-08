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

WEBHOOK_LOGS_DIR = Path("/var/log/whrouter")

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


app.config["WEBHOOK_FILE_PATH"] = WEBHOOK_LOGS_DIR / _log_file_name()


def _write_webhook_log(payload: Any) -> None:
    """Append the webhook payload to a file.

    Args:
        payload: The payload to write.
    """
    with app.config["WEBHOOK_FILE_PATH"].open("a") as f:
        json.dump(payload, f)
        f.write("\n")


@app.route("/webhook", methods=["POST"])
def handle_github_webhook():
    """Receive a GitHub webhook and append the payload to a file."""
    payload = request.get_json()
    app.logger.info("Received webhook: %s", payload)
    _write_webhook_log(payload)
    return "", 200


if __name__ == "__main__":
    app.logger.addHandler(logging.StreamHandler(sys.stdout))
    app.logger.setLevel(logging.INFO)
    app.run()
