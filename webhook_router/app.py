#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Flask application which receives GitHub webhooks and logs those."""
import json
import logging
import sys

from flask import Flask, request

from webhook_router.validation import verify_signature

WEBHOOK_SIGNATURE_HEADER = "X-Hub-Signature-256"

app = Flask(__name__)
app.config.from_prefixed_env()


@app.route("/webhook", methods=["POST"])
def handle_github_webhook() -> tuple[str, int]:
    """Receive a GitHub webhook and append the payload to a file.

    Returns:
        A tuple containing an empty string and 200 status code.
    """
    if secret := app.config.get("WEBHOOK_SECRET"):
        if not (signature := request.headers.get(WEBHOOK_SIGNATURE_HEADER)):
            app.logger.debug(
                "X-Hub-signature-256 header is missing in request from %s", request.origin
            )
            return "X-Hub-signature-256 header is missing!", 403

        if not verify_signature(
            payload=request.data, secret_token=secret, signature_header=signature
        ):
            app.logger.debug("Signature validation failed in request from %s", request.origin)
            return "Signature validation failed!", 403
    payload = request.get_json()
    app.logger.debug("Received webhook: %s", payload)
    app.logger.info(json.dumps(payload))
    return "", 200


# Exclude from coverage since unit tests should not run as __main__
if __name__ == "__main__":  # pragma: no cover
    # Start development server
    app.logger.addHandler(logging.StreamHandler(sys.stdout))
    app.logger.setLevel(logging.DEBUG)
    app.run()
