#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Redeliver failed webhooks since a given time. Only webhooks with action type queued are redelivered (as the others are not routable). """
import argparse
import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Iterator

from github import BadCredentialsException, Github, GithubException, RateLimitExceededException
from github.Auth import AppAuth, AppInstallationAuth, Token
from pydantic import BaseModel

from webhook_router.app import SUPPORTED_GITHUB_EVENT
from webhook_router.router import ROUTABLE_JOB_STATUS

OK_STATUS = "OK"

logger = logging.getLogger(__name__)


class GithubAppAuthDetails(BaseModel):
    """The details to authenticate with Github using a Github App.

    Attributes:
        app_id: The Github App (or client) ID.
        installation_id: The installation ID of the Github App.
        private_key: The private key to authenticate with Github.
    """

    app_id: int | str  # app id is an int but client id is a string
    installation_id: int
    private_key: str


GithubToken = str
GithubAuthDetails = GithubAppAuthDetails | GithubToken


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
class _WebhookDelivery:
    """The details of a webhook delivery.

    Attributes:
        id: The identifier of the delivery.
        status: The status of the delivery.
        delivered_at: The time the delivery was made.
        action: The action type of the delivery. See https://docs.github.com/en/webhooks/webhook-events-and-payloads#workflow_job for possible values for the workflow_job event
        event: The event type of the delivery.
    """

    id: int
    status: str
    delivered_at: datetime
    action: str
    event: str


class RedeliveryError(Exception):
    """Raised when an error occurs during redelivery."""


def _github_api_exc_decorator(func):
    """Decorator to handle GitHub API exceptions."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
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

    return wrapper


@_github_api_exc_decorator
def redeliver_failed_webhook_deliveries(
    github_auth: GithubAuthDetails, webhook_address: WebhookAddress, since_seconds: int
) -> int:
    """Redeliver failed webhook deliveries since a given time.

    Args:
        github_auth: The GitHub authentication details used to interact with the Github API.
        webhook_address: The data to identify the webhook.
        since_seconds: The amount of seconds to look back for failed deliveries.

    Returns:
        The number of failed webhook deliveries redelivered.

    Raises:
        RedeliveryError: If an error occurs during redelivery.
    """
    github = _get_github_client(github_auth)

    deliveries = _get_deliveries(github_client=github, webhook_address=webhook_address)
    since_datetime = datetime.now(tz=timezone.utc) - timedelta(seconds=since_seconds)
    deliver_count = 0
    for delivery in deliveries:
        if delivery.delivered_at < since_datetime:
            break

        if (
            delivery.status != OK_STATUS
            and delivery.action == ROUTABLE_JOB_STATUS
            and delivery.event == SUPPORTED_GITHUB_EVENT
        ):
            _redeliver(
                github_client=github, webhook_address=webhook_address, delivery_id=delivery.id
            )
            deliver_count += 1
    return deliver_count


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

    app_auth = AppAuth(app_id=github_auth.app_id, private_key=github_auth.private_key)
    app_installation_auth = AppInstallationAuth(
        app_auth=app_auth, installation_id=github_auth.installation_id
    )
    return Github(auth=app_installation_auth)


def _get_deliveries(
    github_client: Github, webhook_address: WebhookAddress
) -> Iterator[_WebhookDelivery]:
    """Get webhook deliveries.

    Args:

    Returns:
        The webhook deliveries since the given time.
    """
    webhook_origin = (
        github_client.get_repo(webhook_address.github_org)
        if webhook_address.github_repo
        else github_client.get_organization(webhook_address.github_org)
    )
    deliveries = webhook_origin.get_hook_deliveries(webhook_address.id)
    for delivery in deliveries:
        yield _WebhookDelivery(
            id=delivery.id,
            status=delivery.status,
            delivered_at=delivery.delivered_at,
            action=delivery.action,
            event=delivery.event,
        )


def _redeliver(github_client: Github, webhook_address: WebhookAddress, delivery_id: int) -> None:
    """Redeliver a webhook delivery.

    Args:
        github_auth: The GitHub authentication details used to interact with the Github API.
        webhook_address: The data to identify the webhook.
        delivery_id: The identifier of the webhook delivery.
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=f"{__doc__}. The script assumes github app auth details to be parsed as json via stdin. The format has to be a json object with either the only key 'token' or the keys 'app_id', 'installation_id' and 'private_key'.,"
        f"depending on the authentication method (github token vs github app auth) used."
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

    # read the github auth details from stdin for security reasons
    github_auth_details_raw = input()

    try:
        github_auth_json = json.loads(github_auth_details_raw)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse github auth details: %s", exc)
        print(
            "Failed to parse github auth details, assuming a json with either the only key 'token' or the keys 'app_id', 'installation_id' and 'private_key'",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if "token" in github_auth_json:
        github_auth = github_auth_json["token"]
    else:
        try:
            github_auth = GithubAppAuthDetails(**github_auth_json)
        except ValueError as exc:
            logger.error("Failed to parse github auth details: %s", exc)
            print("Failed to parse github auth details", file=sys.stderr)
            raise SystemExit(1)

    webhook_address = WebhookAddress(
        github_org=args.github_path.split("/")[0],
        github_repo=args.github_path.split("/")[1] if "/" in args.github_path else None,
        id=args.webhook_id,
    )

    try:
        redeliver_count = redeliver_failed_webhook_deliveries(
            github_auth=github_auth, webhook_address=webhook_address, since_seconds=args.since
        )
    except RedeliveryError as exc:
        logger.exception("Failed to redeliver webhook deliveries")
        print(f"Failed to redeliver webhook deliveries: {exc}", file=sys.stderr)
        raise SystemExit(1)
    print(json.dumps({"redelivered": redeliver_count}))
