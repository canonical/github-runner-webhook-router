#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Init module which contain common dataclasses for the webhook redelivery implementation."""

from dataclasses import dataclass
from datetime import datetime


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
    id: str


@dataclass
class WebhookDeliveryDetails:
    """The details of a webhook delivery.

    Attributes:
        id: The delivery identifier.
        delivered_at: The time the delivery was attempted.
        success: Whether the delivery was successful.
    """

    id: str
    delivered_at: datetime
    success: bool
