#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Implementation of the webhook redelivery logic."""

from datetime import datetime

from github import Github
from webhook_redelivery import WebhookAddress


class RedeliveryError(Exception):
    """Raised when an error occurs during redelivery."""


def redeliver_failed_webhooks(
    github_client: Github, webhook_address: WebhookAddress, since: datetime
) -> int:
    """Redeliver failed webhooks since a given time.

    Args:
        github_client: The GitHub client used for interactions with Github.
        webhook_address: The data to identify the webhook.
        since: The time to redeliver failed webhooks since.

    Returns:
        The number of failed webhooks redelivered.
    """
