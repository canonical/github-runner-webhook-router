#!/usr/bin/env python3
#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Flask Charm entrypoint."""
import json
import logging
import typing

import ops
import paas_charm.flask
from ops.pebble import ExecError

logger = logging.getLogger(__name__)


class FlaskCharm(paas_charm.flask.Charm):
    """Flask Charm service."""

    def __init__(self, *args: typing.Any) -> None:
        """Initialize the instance.

        Args:
            args: passthrough to CharmBase.
        """
        super().__init__(*args)
        self.framework.observe(
            self.on.redeliver_failed_webhooks_action, self._on_redeliver_failed_webhooks_action
        )

    def _on_redeliver_failed_webhooks_action(self, event: ops.charm.ActionEvent) -> None:
        """Redeliver failed webhooks since a given time."""
        logger.info("Redelivering failed webhooks.")
        # Implement the redeliver_failed_webhooks_action here.
        container: ops.Container = self.unit.get_container("flask-app")
        since_seconds = event.params["since"]
        github_path = event.params["github-path"]
        webhook_id = event.params["webhook-id"]
        github_token_secret_id = event.params["github-token-secret"]
        github_token_secret = self.model.get_secret(id=github_token_secret_id)
        github_token_secret_data = github_token_secret.get_content()
        try:
            stdout, _ = container.exec(
                [
                    "/usr/bin/python3",
                    "/flask/app/webhook_redelivery.py",
                    "--since",
                    str(since_seconds),
                    "--github-path",
                    github_path,
                    "--webhook-id",
                    str(webhook_id),
                ],
                stdin=json.dumps({"token": github_token_secret_data["token"]}),
            ).wait_output()
            logger.info("Got %s", stdout)
            result = json.loads(
                stdout.rstrip().split("\n")[-1]
            )  # only consider the last line as result
            event.set_results(result)
        except ExecError as exc:
            logger.warning("Webhook redelivery failed, script reported: %s", exc.stderr)
            event.fail("Webhooks redelivery failed. Look at juju debug-log for more information.")

        # logger.info("Failed webhooks redelivered.")


if __name__ == "__main__":
    ops.main.main(FlaskCharm)
