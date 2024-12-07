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

GITHUB_TOKEN_PARAM_NAME = "github-token-secret" # TODO rename to -secret-id
GITHUB_APP_ID_PARAM_NAME = "github-app-id"
GITHUB_APP_INSTALLATION_ID_PARAM_NAME = "github-app-installation-id"
GITHUB_APP_PRIVATE_KEY_PARAM_NAME = "github-app-private-key-secret"

MISSING_GITHUB_PARAMS_ERR_MSG = (
    f"Either the {GITHUB_TOKEN_PARAM_NAME} or not all of {GITHUB_APP_ID_PARAM_NAME},"
    f" {GITHUB_APP_INSTALLATION_ID_PARAM_NAME}, {GITHUB_APP_PRIVATE_KEY_PARAM_NAME} "
    f"parameters were provided or are empty, "
    "the vparameters are needed for interactions with GitHub, "
)
NOT_ALL_GITHUB_APP_PARAMS_ERR_MSG = (
    f"Not all of {GITHUB_APP_ID_PARAM_NAME}, {GITHUB_APP_INSTALLATION_ID_PARAM_NAME},"
    f" {GITHUB_APP_PRIVATE_KEY_PARAM_NAME} environment variables were provided, "
)
# the following is no hardcoded password
PROVIDED_GITHUB_TOKEN_AND_APP_PARAMS_ERR_MSG = (  # nosec
    "Provided github app config and github token, only one of them should be provided, "
)

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
        since_seconds = event.params["since"]
        github_path = event.params["github-path"]
        webhook_id = event.params["webhook-id"]
        github_token_secret_id = event.params.get("github-token-secret")
        github_app_id = event.params.get("github-app-id")
        github_app_installation_id = event.params.get("github-app-installation-id")
        github_app_private_key_secret_id = event.params.get("github-app-private-key-secret")

        try:
            auth_details = self._get_auth_details(
                github_token_secret_id, github_app_id, github_app_installation_id, github_app_private_key_secret_id
            )
        except _ActionParamsInvalidError as exc:
            logger.warning("Webhook redelivery failed, invalid action parameters: %s", exc)
            event.fail("Invalid action parameters passed. Look at juju debug-log for more information.")
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
                stdin=json.dumps(auth_details),
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

    def _get_auth_details(
            self,
        github_token_secret_id: str | None,
        github_app_id: str | None,
        github_app_installation_id_str: str | None,
        github_app_private_key: str | None,
    ) -> dict:
        """Get the authentication details

        Args:
            github_token_secret_id: The GitHub token secret ID.
            github_app_id: The GitHub App ID or Client ID.
            github_app_installation_id_str: The GitHub App Installation ID as a string.
            github_app_private_key: The GitHub App private key.

        Returns: a dict which can be passed to the webhook redelivery script as JSON.

        Raises: _ActionParamsInvalidError If the configuration is invalid.
        """
        if not github_token_secret_id and not (
            github_app_id or github_app_installation_id_str or github_app_private_key
        ):
            raise _ActionParamsInvalidError(
                f"{MISSING_GITHUB_PARAMS_ERR_MSG}"
                f"got: {github_token_secret_id!r}, {github_app_id!r},"
                f" {github_app_installation_id_str!r}, {github_app_private_key!r}"
            )
        if github_token_secret_id and (
            github_app_id or github_app_installation_id_str or github_app_private_key
        ):
            raise _ActionParamsInvalidError(
                f"{PROVIDED_GITHUB_TOKEN_AND_APP_PARAMS_ERR_MSG}"
                f"got: {github_token_secret_id!r}, {github_app_id!r}, {github_app_installation_id_str!r},"
                f" {github_app_private_key!r}"
            )

        if github_app_id or github_app_installation_id_str or github_app_private_key:
            if not (github_app_id and github_app_installation_id_str and github_app_private_key):
                raise _ActionParamsInvalidError(
                    f"{NOT_ALL_GITHUB_APP_PARAMS_ERR_MSG}"
                    f"got: {github_app_id!r}, {github_app_installation_id_str!r}, "
                    f"{github_app_private_key!r}"
                )

        if github_token_secret_id:
            github_token_secret = self.model.get_secret(id=github_token_secret_id)
            github_token_secret_data = github_token_secret.get_content()
            return {"token": github_token_secret_data["token"]}
        return self._get_github_app_installation_auth_details(
            github_app_id, github_app_installation_id_str, github_app_private_key
        )


    def _get_github_app_installation_auth_details(
            self,
        github_app_id: str, github_app_installation_id_str: str, github_app_private_key_secret_id: str
    ) -> dict:
        """Get the Github app installation auth details.

        Args:
            github_app_id: The GitHub App ID or Client ID.
            github_app_installation_id_str: The GitHub App Installation ID as a string.
            github_app_private_key_secret_id: The GitHub App private key secret id

        Returns:
            a dict which can be passed to the webhook redelivery script as JSON.

    Raises: _ActionParamsInvalidError If the configuration is invalid.
        """
        try:
            github_app_installation_id = int(github_app_installation_id_str)
        except ValueError as exc:
            raise _ActionParamsInvalidError(
                f"Invalid github app installation id {github_app_installation_id_str!r}, "
                f"it should be an integer."
            ) from exc
        github_app_private_key_secret = self.model.get_secret(id=github_app_private_key_secret_id)
        github_app_private_key_secret_data = github_app_private_key_secret.get_content()
        return {
            "app_id": github_app_id,
            "installation_id": github_app_installation_id,
            "private_key": github_app_private_key_secret_data["private-key"],
        }

if __name__ == "__main__":
    ops.main.main(FlaskCharm)
