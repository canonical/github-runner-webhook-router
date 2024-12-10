#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Redeliver failed webhooks since a given time.

Only webhooks with action type queued are redelivered (as the others are not routable).
"""
import argparse
import json
import logging
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

OK_STATUS = "OK"

P = ParamSpec("P")
R = TypeVar("R")

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
class _WebhookDelivery:
    """The details of a webhook delivery.

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

    Raises:  # noqa: DCO051 its a public fct so we should mention that this exc is raised
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
        if None in (
            delivery.id,
            delivery.status,
            delivery.delivered_at,
            delivery.action,
            delivery.event,
        ):
            # all these fields are required per API schema, this shouldn't be expected
            raise AssertionError("The webhook delivery is missing required fields.")
        yield _WebhookDelivery(
            id=delivery.id,  # type: ignore
            status=delivery.status,  # type: ignore
            delivered_at=delivery.delivered_at,  # type: ignore
            action=delivery.action,  # type: ignore
            event=delivery.event,  # type: ignore
        )


def _redeliver(github_client: Github, webhook_address: WebhookAddress, delivery_id: int) -> None:
    """Redeliver a webhook delivery.

    Args:
        github_client: The GitHub client used to interact with the Github API.
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


def _main() -> None:
    """Run the module as script."""
    args = _arg_parsing()

    try:
        redelivery_count = redeliver_failed_webhook_deliveries(
            github_auth=args.github_auth_details,
            webhook_address=args.webhook_address,
            since_seconds=args.since,
        )
    except RedeliveryError as exc:
        logger.exception("Failed to redeliver webhook deliveries")
        print(f"Failed to redeliver webhook deliveries: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(_create_json_output(redelivery_count))


def _arg_parsing() -> _ParsedArgs:
    """Parse the command line arguments."""
    parser = argparse.ArgumentParser(
        description=f"{__doc__}. The script returns the amount of redelivered webhooks in JSON"
        "format.The script assumes github app auth details to be parsed as json"
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

    # read the github auth details from stdin for security reasons
    github_auth_details_raw = input()

    try:
        github_auth_details_json = json.loads(github_auth_details_raw)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse github auth details: %s", exc)
        print(
            "Failed to parse github auth details, assuming a json with either the only key"
            " 'token' or the keys 'app_id', 'installation_id' and 'private_key'",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    if "token" in github_auth_details_json:
        github_auth_details = github_auth_details_json["token"]
    else:
        try:
            github_auth_details = GithubAppAuthDetails(**github_auth_details_json)
        except ValueError as exc:
            logger.error("Failed to parse github auth details: %s", exc)
            print("Failed to parse github auth details", file=sys.stderr)
            raise SystemExit(1) from exc

    webhook_address = WebhookAddress(
        github_org=args.github_path.split("/")[0],
        github_repo=args.github_path.split("/")[1] if "/" in args.github_path else None,
        id=args.webhook_id,
    )

    return _ParsedArgs(
        since=args.since, github_auth_details=github_auth_details, webhook_address=webhook_address
    )


def _create_json_output(redelivery_count: int) -> str:
    """Create a JSON output as strong  with the redelivery count.

    Args:
        redelivery_count: The number of redelivered webhooks.
    """
    return json.dumps({"redelivered": redelivery_count})


if __name__ == "__main__":
    _main()
