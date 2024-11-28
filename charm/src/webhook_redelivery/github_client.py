#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Interactions with the GitHub API."""

from datetime import datetime
from typing import Iterator

from github import Github
from webhook_redelivery import WebhookAddress, WebhookDeliveryDetails


class GithubApiError(Exception):
    """An error occurred while interacting with the GitHub API."""


def get() -> Github:
    """Get a GitHub client.

    Returns:
        A GitHub client that is configured with a token or GitHub app from the environment.

    Raises:
        ConfigurationError: If the GitHub auth config is not valid.
    """


def get_webhook_deliveries(
    github_client: Github, webhook_address: WebhookAddress, since: datetime
) -> Iterator[WebhookDeliveryDetails]:
    """Get webhook deliveries for a webhook address since a given time.

    Args:
        github_client: The GitHub client to use for interactions with GitHub.
        webhook_address: The data to identify the webhook.
        since: The time to get deliveries since.

    Returns:
        An iterator of webhook deliveries.
    """


def redeliver_webhook(
    github_client: Github, webhook_address: WebhookAddress, delivery_id: str
) -> None:
    """Redeliver a webhook delivery.

    Args:
        github_client: The GitHub client to use for interactions with GitHub.
        webhook_address: The data to identify the webhook.
        delivery_id: The delivery identifier.
    """
