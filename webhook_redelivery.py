#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Redeliver failed webhooks."""


from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Iterator

from github import Github
from github.Auth import AppAuth, AppInstallationAuth, Token

OK_STATUS = "OK"

@dataclass
class GithubAppAuthDetails:
    """The details to authenticate with Github using a Github App.

    Attributes:
        app_id: The Github App (or client) ID.
        installation_id: The installation ID of the Github App.
        private_key: The private key to authenticate with Github.
    """

    app_id: str
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
    """

    id: int
    status: str
    delivered_at: datetime


class RedeliveryError(Exception):
    """Raised when an error occurs during redelivery."""


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

        if delivery.status != OK_STATUS:
            _redeliver(github_client=github, webhook_address=webhook_address, delivery_id=delivery.id)
            deliver_count += 1
    return deliver_count


def _get_github_client(github_auth: GithubAuthDetails) -> Github:
    """Get a Github client.

    Args:
        github_auth: The Github authentication details.

    Returns:
        The Github client.
    """
    if isinstance(github_auth, GithubToken):
        return Github(auth=Token(github_auth))

    app_auth = AppAuth(app_id=github_auth.app_id, private_key=github_auth.private_key)
    app_installation_auth = AppInstallationAuth(app_auth=app_auth, installation_id=github_auth.installation_id)
    return Github(auth=app_installation_auth)

def _get_deliveries(
    github_client: Github, webhook_address: WebhookAddress
) -> Iterator[_WebhookDelivery]:
    """Get webhook deliveries since a given time.

    Args:

    Returns:
        The webhook deliveries since the given time.
    """
    # TODO: Implement the logic for org webhooks.
    repository = github_client.get_repo(f"{webhook_address.github_org}/{webhook_address.github_repo}")
    deliveries = repository.get_hook_deliveries(webhook_address.id)
    for delivery in deliveries:
        yield _WebhookDelivery(
            id=delivery.id,
            status=delivery.status,
            delivered_at=delivery.delivered_at,
        )

def _redeliver(
    github_client: Github, webhook_address: WebhookAddress, delivery_id: int
) -> None:
    """Redeliver a webhook delivery.

    Args:
        github_auth: The GitHub authentication details used to interact with the Github API.
        webhook_address: The data to identify the webhook.
        delivery_id: The identifier of the webhook delivery.

    Raises:
        RedeliveryError: If an error occurs during redelivery.
    """
    url = f"/repos/{webhook_address.github_org}/{webhook_address.github_repo}/hooks/{webhook_address.id}/deliveries/{delivery_id}/attempts"
    github_client.requester.requestJsonAndCheck("POST", url)

if __name__ == '__main__':
    # Argument parsing and main entrypoint for the script.
    pass
