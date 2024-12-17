#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Redeliver failed webhooks since a given time.

Only webhooks with action type queued are redelivered (as the others are not routable).
"""
import argparse
import json
import logging
import os
import sys
from collections import namedtuple
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Callable, Iterator, ParamSpec, TypeVar

from github import BadCredentialsException, Github, GithubException, RateLimitExceededException
from github.Auth import AppAuth, AppInstallationAuth, Token
from pydantic import BaseModel

from webhook_router.app import SUPPORTED_GITHUB_EVENT
from webhook_router.router import ROUTABLE_JOB_STATUS

GITHUB_TOKEN_ENV_NAME = "GITHUB_TOKEN"
GITHUB_APP_CLIENT_ID_ENV_NAME = "GITHUB_APP_CLIENT_ID"
GITHUB_APP_INSTALLATION_ID_ENV_NAME = "GITHUB_APP_INSTALLATION_ID"
GITHUB_APP_PRIVATE_KEY_ENV_NAME = "GITHUB_APP_PRIVATE_KEY"

OK_STATUS = "OK"

P = ParamSpec("P")
R = TypeVar("R")

logger = logging.getLogger(__name__)


class GithubAppAuthDetails(BaseModel):
    """The details to authenticate with Github using a Github App.

    Attributes:
        client_id: The Github App client ID.
        installation_id: The installation ID of the Github App.
        private_key: The private key to authenticate with Github.
    """

    client_id: str
    installation_id: int
    private_key: str


GithubToken = str
GithubAuthDetails = GithubAppAuthDetails | GithubToken

_ParsedArgs = namedtuple("_ParsedArgs", ["since", "github_auth_details", "webhook_address"])


@dataclass
class WebhookAddress:
    """The address details to identify the webhook.

    Attributes:
        github_org: Github organisation where the webhook is registered.
        github_repo: Github repository, where the webhook is registered. Only applicable for
            repository webhooks.
        id: The identifier of the webhook.
    """

    github_org: str
    github_repo: str | None
    id: int


@dataclass
class _WebhookDeliveryAttempts:
    """The details of a webhook delivery attempt.

    Attributes:
        id: The identifier of the delivery.
        status: The status of the delivery.
        delivered_at: The time the delivery was made.
        action: The action type of the delivery.
         See https://docs.github.com/en/webhooks/webhook-events-and-payloads#workflow_job for
         possible values for the workflow_job event
        event: The event type of the delivery.
    """

    id: int
    status: str
    delivered_at: datetime
    action: str
    event: str


class RedeliveryError(Exception):
    """Raised when an error occurs during redelivery."""


class ArgParseError(Exception):
    """Raised when an error occurs during argument parsing."""


def main() -> None:  # pragma: no cover this is checked by integration tests
    """Run the module as script."""
    args = _arg_parsing()

    redelivery_count = _redeliver_failed_webhook_delivery_attempts(
        github_auth=args.github_auth_details,
        webhook_address=args.webhook_address,
        since_seconds=args.since,
    )

    print(_create_json_output(redelivery_count))


def _arg_parsing() -> _ParsedArgs:  # pragma: no cover this is checked by integration tests
    """Parse the command line arguments.

    Raises:
        ArgParseError: If the arguments are invalid.

    Returns:
        The parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description=f"{__doc__}. The script returns the amount of redelivered webhooks in JSON"
        "format.The script assumes github app auth details to be given via env variables"
        " via stdin. The format has to be a json object with either the only key"
        " 'token' or the keys 'app_id', 'installation_id' and 'private_key'.,"
        " depending on the authentication method (github token vs github app auth) used."
    )
    parser.add_argument(
        "--since",
        type=int,
        help="The amount of seconds to look back for failed deliveries.",
        required=True,
    )
    parser.add_argument(
        "--github-path",
        type=str,
        help=(
            "The path of the organisation or repository where the webhooks are registered. Should"
            "be in the format of <organisation> or <organisation>/<repository>."
        ),
        required=True,
    )
    parser.add_argument(
        "--webhook-id", type=int, help="The identifier of the webhook.", required=True
    )
    args = parser.parse_args()

    github_app_client_id = os.getenv(GITHUB_APP_CLIENT_ID_ENV_NAME)
    github_app_installation_id = os.getenv(GITHUB_APP_INSTALLATION_ID_ENV_NAME)
    github_app_private_key = os.getenv(GITHUB_APP_PRIVATE_KEY_ENV_NAME)
    github_token = os.getenv(GITHUB_TOKEN_ENV_NAME)

    github_auth_details: GithubAuthDetails
    if github_token:
        github_auth_details = github_token
    elif github_app_client_id and github_app_installation_id and github_app_private_key:
        try:
            github_auth_details = GithubAppAuthDetails(
                client_id=github_app_client_id,
                installation_id=int(github_app_installation_id),
                private_key=github_app_private_key,
            )
        except ValueError as exc:
            raise ArgParseError("Failed to parse github auth details") from exc
    else:
        raise ArgParseError(
            "Github auth details are not specified completely. "
            "Am missing github_token or complete set of app auth parameters."
            f" Got github_app_client_id = {github_app_client_id},"
            f" github_app_installation_id = {github_app_installation_id},"
            f" github_app_private_key = {'***' if github_app_private_key else None},"
            f" github_token = None",
        )
    webhook_address = WebhookAddress(
        github_org=args.github_path.split("/")[0],
        github_repo=args.github_path.split("/")[1] if "/" in args.github_path else None,
        id=args.webhook_id,
    )

    return _ParsedArgs(
        since=args.since, github_auth_details=github_auth_details, webhook_address=webhook_address
    )


# this is checked by integration tests
def _create_json_output(redelivery_count: int) -> str:  # pragma: no cover
    """Create a JSON output as strong  with the redelivery count.

    Args:
        redelivery_count: The number of redelivered webhooks.
    """
    return json.dumps({"redelivered": redelivery_count})


def _github_api_exc_decorator(func: Callable[P, R]) -> Callable[P, R]:
    """Decorator to handle GitHub API exceptions."""

    @wraps(func)
    def _wrapper(*posargs: P.args, **kwargs: P.kwargs) -> R:
        """Wrap the function to handle Github API exceptions.

        Catch Github API exceptions and raise an appropriate RedeliveryError instead.


        Raises:
            RedeliveryError: If an error occurs during redelivery.

        Returns:
            The result of the origin function when no github error occurs.
        """
        try:
            return func(*posargs, **kwargs)
        except BadCredentialsException as exc:
            logging.error("Github client credentials error: %s", exc, exc_info=exc)
            raise RedeliveryError(
                "The github client returned a Bad Credential error, "
                "please ensure credentials are set and have proper access rights."
            ) from exc
        except RateLimitExceededException as exc:
            logging.error("Github rate limit exceeded error: %s", exc, exc_info=exc)
            raise RedeliveryError(
                "The github client is returning a Rate Limit Exceeded error, "
                "please wait before retrying."
            ) from exc
        except GithubException as exc:
            logging.error("Github API error: %s", exc, exc_info=exc)
            raise RedeliveryError(
                "The github client encountered an error. Please have a look at the logs."
            ) from exc

    return _wrapper


@_github_api_exc_decorator
def _redeliver_failed_webhook_delivery_attempts(
    github_auth: GithubAuthDetails, webhook_address: WebhookAddress, since_seconds: int
) -> int:
    """Redeliver failed webhook deliveries since a given time.

    Args:
        github_auth: The GitHub authentication details used to interact with the Github API.
        webhook_address: The data to identify the webhook.
        since_seconds: The amount of seconds to look back for failed deliveries.

    Returns:
        The number of failed webhook deliveries redelivered.

    """
    github = _get_github_client(github_auth)

    deliveries = _iter_delivery_attempts(github_client=github, webhook_address=webhook_address)
    since_datetime = datetime.now(tz=timezone.utc) - timedelta(seconds=since_seconds)
    failed_deliveries = _filter_for_failed_attempts(
        deliveries=deliveries, since_datetime=since_datetime
    )
    redelivered_count = _redeliver_attempts(
        deliveries=failed_deliveries, github_client=github, webhook_address=webhook_address
    )

    return redelivered_count


# Github App authentication is not tested in unit tests, but in integration tests.
def _get_github_client(github_auth: GithubAuthDetails) -> Github:  # pragma: no cover
    """Get a Github client.

    Args:
        github_auth: The Github authentication details.

    Returns:
        The Github client.
    """
    if isinstance(github_auth, GithubToken):
        return Github(auth=Token(github_auth))

    app_auth = AppAuth(app_id=github_auth.client_id, private_key=github_auth.private_key)
    app_installation_auth = AppInstallationAuth(
        app_auth=app_auth, installation_id=github_auth.installation_id
    )
    return Github(auth=app_installation_auth)


def _iter_delivery_attempts(
    github_client: Github, webhook_address: WebhookAddress
) -> Iterator[_WebhookDeliveryAttempts]:
    """Iterate over webhook delivery attempts.

    Args:
        github_client: The GitHub client used to interact with the Github API.
        webhook_address: The data to identify the webhook.
    """
    webhook_origin = (
        github_client.get_repo(f"{webhook_address.github_org}/{webhook_address.github_repo}")
        if webhook_address.github_repo
        else github_client.get_organization(webhook_address.github_org)
    )
    deliveries = webhook_origin.get_hook_deliveries(webhook_address.id)
    for delivery in deliveries:
        # we check that the API is really returning the expected fields with non-null vals
        # as pygithub is not doing this validation for us
        required_fields = {"id", "status", "delivered_at", "action", "event"}
        none_fields = {
            field for field in required_fields if getattr(delivery, field, None) is None
        }
        if none_fields:
            raise AssertionError(f"The webhook delivery is missing required fields: {none_fields}")
        yield _WebhookDeliveryAttempts(
            id=delivery.id,  # type: ignore
            status=delivery.status,  # type: ignore
            delivered_at=delivery.delivered_at,  # type: ignore
            action=delivery.action,  # type: ignore
            event=delivery.event,  # type: ignore
        )


def _filter_for_failed_attempts(
    deliveries: Iterator[_WebhookDeliveryAttempts], since_datetime: datetime
) -> Iterator[_WebhookDeliveryAttempts]:
    """Filter webhook delivery attempts for failed deliveries since a given time.

    Args:
        deliveries: The webhook delivery attempts.
        since_datetime: The time to look back for failed deliveries.
    """
    for delivery in deliveries:
        if delivery.delivered_at < since_datetime:
            break

        if (
            delivery.status != OK_STATUS
            and delivery.action == ROUTABLE_JOB_STATUS
            and delivery.event == SUPPORTED_GITHUB_EVENT
        ):
            yield delivery


def _redeliver_attempts(
    deliveries: Iterator[_WebhookDeliveryAttempts],
    github_client: Github,
    webhook_address: WebhookAddress,
) -> int:
    """Redeliver failed webhook deliveries since a given time.

    Args:
        deliveries: The webhook delivery attempts.
        github_client: The GitHub client used to interact with the Github API.
        webhook_address: The data to identify the webhook.

    Returns:
        The number of failed webhook deliveries redelivered.
    """
    deliver_count = 0
    for delivery in deliveries:
        _redeliver_attempt(
            github_client=github_client, webhook_address=webhook_address, delivery_id=delivery.id
        )
        deliver_count += 1
    return deliver_count


def _redeliver_attempt(
    github_client: Github, webhook_address: WebhookAddress, delivery_id: int
) -> None:
    """Redeliver a webhook delivery.

    Args:
        github_client: The GitHub client used to interact with the Github API.
        webhook_address: The data to identify the webhook.
        delivery_id: The identifier of the webhook delivery to redeliver.
    """
    # pygithub doesn't support the endpoint so we have to use the requester directly to perform
    # a raw request: https://pygithub.readthedocs.io/en/stable/utilities.html#raw-requests
    path_base = (
        f"/repos/{webhook_address.github_org}/{webhook_address.github_repo}"
        if webhook_address.github_repo
        else f"/orgs/{webhook_address.github_org}"
    )
    url = f"{path_base}/hooks/{webhook_address.id}/deliveries/{delivery_id}/attempts"
    github_client.requester.requestJsonAndCheck("POST", url)


if __name__ == "__main__":  # pragma: no cover this is checked by integration tests
    try:
        main()
    except ArgParseError as exc:
        logger.exception("Argument parsing failed: %s", exc)
        sys.exit(1)
    except RedeliveryError as exc:
        logger.exception("Webhook redelivery failed: %s", exc)
        sys.exit(1)
