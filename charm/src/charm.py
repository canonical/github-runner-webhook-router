#!/usr/bin/env python3
#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Flask Charm entrypoint."""
import json
import logging
import typing

import ops

# we don't have the types for paas_charm.flask
import paas_charm.flask  # type: ignore
from ops import ActionEvent
from ops.pebble import ExecError

logger = logging.getLogger(__name__)


SCRIPT_ARG_PARSE_ERROR_EXIT_CODE = 1
SINCE_PARAM_NAME = "since"
GITHUB_PATH_PARAM_NAME = "github-path"
WEBHOOK_ID_PARAM_NAME = "webhook-id"
GITHUB_TOKEN_SECRET_ID_PARAM_NAME = "github-token-secret-id"
GITHUB_APP_CLIENT_ID_PARAM_NAME = "github-app-client-id"
GITHUB_APP_INSTALLATION_ID_PARAM_NAME = "github-app-installation-id"
GITHUB_APP_PRIVATE_KEY_SECRET_ID_PARAM_NAME = "github-app-private-key-secret-id"
GITHUB_TOKEN_ENV_NAME = "GITHUB_TOKEN"
GITHUB_APP_CLIENT_ID_ENV_NAME = "GITHUB_APP_CLIENT_ID"
GITHUB_APP_INSTALLATION_ID_ENV_NAME = "GITHUB_APP_INSTALLATION_ID"
GITHUB_APP_PRIVATE_KEY_ENV_NAME = "GITHUB_APP_PRIVATE_KEY"


class _ActionParamsInvalidError(Exception):
    """Raised when the action parameters are invalid."""


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
        container: ops.Container = self.unit.get_container("flask-app")
        since_seconds = event.params[SINCE_PARAM_NAME]
        github_path = event.params[GITHUB_PATH_PARAM_NAME]
        webhook_id = event.params[WEBHOOK_ID_PARAM_NAME]

        try:
            auth_env = self._get_github_auth_env(event)
        except _ActionParamsInvalidError as exc:
            event.fail(f"Invalid action parameters passed: {exc}")
            return
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
                environment=auth_env,
            ).wait_output()
            logger.info("Got %s", stdout)
            result = json.loads(
                stdout.rstrip().split("\n")[-1]
            )  # only consider the last line as result
            event.set_results(result)
        except ExecError as exc:
            logger.warning("Webhook redelivery failed, script reported: %s", exc.stderr)
            if exc.exit_code == SCRIPT_ARG_PARSE_ERROR_EXIT_CODE:
                event.fail(f"Argument parsing failed. {exc.stderr}")
            else:
                event.fail(
                    "Webhooks redelivery failed. Look at the juju logs for more information."
                )

    def _get_github_auth_env(self, event: ActionEvent) -> dict[str, str]:
        """Get the GitHub auth environment variables from the action parameters.

        Args:
            event: The action event.

        Returns:
            The GitHub auth environment variables used by the script in the workload.
        """
        github_token_secret_id = event.params.get(GITHUB_TOKEN_SECRET_ID_PARAM_NAME)
        github_app_client_id = event.params.get(GITHUB_APP_CLIENT_ID_PARAM_NAME)
        github_app_installation_id = event.params.get(GITHUB_APP_INSTALLATION_ID_PARAM_NAME)
        github_app_private_key_secret_id = event.params.get(
            GITHUB_APP_PRIVATE_KEY_SECRET_ID_PARAM_NAME
        )

        github_token = (
            self._get_secret_value(github_token_secret_id, "token")
            if github_token_secret_id
            else None
        )
        github_app_private_key = (
            self._get_secret_value(github_app_private_key_secret_id, "private-key")
            if github_app_private_key_secret_id
            else None
        )

        env_vars = {
            GITHUB_TOKEN_ENV_NAME: github_token,
            GITHUB_APP_CLIENT_ID_ENV_NAME: github_app_client_id,
            GITHUB_APP_INSTALLATION_ID_ENV_NAME: (
                str(github_app_installation_id) if github_app_installation_id else None
            ),
            GITHUB_APP_PRIVATE_KEY_ENV_NAME: github_app_private_key,
        }
        return {k: v for k, v in env_vars.items() if v}

    def _get_secret_value(self, secret_id: str, key: str) -> str:
        """Get the value of a secret.

        Args:
            secret_id: The secret id.
            key: The key of the secret value to extract.

        Returns:
            The secret value.

        Raises:
            _ActionParamsInvalidError: If the secret does not exist
                or the key is not in the secret.
        """
        try:
            secret = self.model.get_secret(id=secret_id)
        except ops.model.ModelError as exc:
            raise _ActionParamsInvalidError(f"Could not access/find secret {secret_id}") from exc
        secret_data = secret.get_content()
        try:
            return secret_data[key]
        except KeyError as exc:
            raise _ActionParamsInvalidError(
                f"Secret {secret_id} does not contain a field called '{key}'."
            ) from exc


if __name__ == "__main__":
    ops.main.main(FlaskCharm)
