#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Redeliver failed webhooks."""


from dataclasses import dataclass


@dataclass
class GithubAppAuthDetails:
    """The details to authenticate with Github using a Github App.

    Attributes:
        app_id: The Github App (or client) ID.
        installation_id: The installation ID of the Github App.
        private_key: The private key to authenticate with Github.
    """

    app_id: str
    installation_id: str
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
    id: str


class RedeliveryError(Exception):
    """Raised when an error occurs during redelivery."""


def redeliver(
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


if __name__ == '__main__':
    # Argument parsing and main entrypoint for the script.
    pass
