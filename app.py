import json
from pathlib import Path
from typing import Any

from flask import Flask, request

import logging
import sys

WEBHOOK_FILE_PATH = Path("/var/log/webhook.log")

app = Flask(__name__)
app.config.from_prefixed_env()

app.config["WEBHOOK_FILE_PATH"] = WEBHOOK_FILE_PATH


def _write_webhook_log(payload: Any) -> None:
    """Write the webhook payload to a file.

    Args:
        payload: The payload to write.
    """
    with app.config["WEBHOOK_FILE_PATH"].open("a") as f:
        json.dump(payload, f)
        f.write("\n")


@app.route('/webhook', methods=['POST'])
def handle_github_webhook():
   payload = request.get_json()
   app.logger.info("Received webhook: %s", payload)
   _write_webhook_log(payload)
   return '', 200


if __name__ == '__main__':
    app.logger.addHandler(logging.StreamHandler(sys.stdout))
    app.logger.setLevel(logging.INFO)
    app.run()
