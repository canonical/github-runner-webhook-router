# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Flask application which receives GitHub webhooks and logs those."""
import functools
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

from flask import Flask, request

from src.validation import SignatureValidationError, verify_signature

WEBHOOK_SIGNATURE_HEADER = "X-Hub-Signature-256"

app = Flask(__name__)
app.config.from_prefixed_env()


webhook_logger = logging.getLogger("webhook_logger")
webhook_secret = os.environ.get("WEBHOOK_SECRET")
if webhook_secret:
    app.config["WEBHOOK_SECRET"] = webhook_secret


def setup_logger(log_file: Path) -> None:
    """Set up the webhook logger to log to a file.

    Args:
        log_file: The log file.
    """
    webhook_logger.handlers.clear()
    fhandler = logging.FileHandler(log_file, delay=True)
    fhandler.setLevel(logging.INFO)
    webhook_logger.addHandler(fhandler)
    webhook_logger.setLevel(logging.INFO)


def _log_filename() -> str:
    """Create the log file name.

    Returns:
        The log file name.
    """
    # We use a unique name to avoid race conditions between multiple instances of the app.
    pid = os.getpid()
    return datetime.now().strftime(f"webhooks.%Y-%m-%d-%H-%M-%S.{pid}.log")


webhook_logs_dir = Path(os.environ.get("WEBHOOK_LOGS_DIR", "/var/log/whrouter"))
setup_logger(log_file=webhook_logs_dir / _log_filename())


def signature_validator(func: Callable[[], tuple[str, int]]) -> Callable[[], tuple[str, int]]:
    """Validate the signature of the incoming request.

    Args:
        func: function to be decorated.

    Returns:
        Decorated function.
    """

    @functools.wraps(func)
    def wrapper() -> tuple[str, int]:
        """Validate the signature of the incoming request.

        Returns:
            A tuple containing an error message and 403 status code if the signature is invalid.
            Otherwise, the result of the decorated function.
        """
        if secret := app.config.get("WEBHOOK_SECRET"):
            request_signature = request.headers.get(WEBHOOK_SIGNATURE_HEADER)
            if request_signature is None:
                return "X-Hub-signature-256 header is missing!", 403
            try:
                verify_signature(
                    payload=request.data, secret_token=secret, signature_header=request_signature
                )
            except SignatureValidationError:
                return "Signature validation failed!", 403
        return func()

    return wrapper


@app.route("/webhook", methods=["POST"])
@signature_validator
def handle_github_webhook() -> tuple[str, int]:
    """Receive a GitHub webhook and append the payload to a file.

    Returns:
        A tuple containing an empty string and 200 status code.
    """
    payload = request.get_json()
    app.logger.debug("Received webhook: %s", payload)
    webhook_logger.log(logging.INFO, json.dumps(payload))
    return "", 200


if __name__ == "__main__":
    # Start development server
    app.logger.addHandler(logging.StreamHandler(sys.stdout))
    app.logger.setLevel(logging.DEBUG)
    app.run()
