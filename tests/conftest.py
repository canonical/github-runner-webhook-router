# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for charm tests."""

from pytest import Parser

CHARM_FILE_PARAM = "--charm-file"
FLASK_APP_IMAGE_PARAM = "--github-runner-webhook-router-image"
USE_EXISTING_APP_PARAM = "--use-existing-app"
GITHUB_TOKEN_PARAM = "--github-token"  # nosec this is no hardcoded password
GITHUB_APP_CLIENT_ID_PARAM = "--github-app-client-id"
GITHUB_APP_INSTALLATION_ID_PARAM_NAME = "--github-app-installation-id"
GITHUB_APP_PRIVATE_KEY_PARAM_NAME = "--github-app-private-key"
WEBHOOK_TEST_REPOSITORY_PARAM = "--webhook-test-repository"


def pytest_addoption(parser: Parser) -> None:
    """Parse additional pytest options.

    Args:
        parser: Pytest parser.
    """
    parser.addoption(CHARM_FILE_PARAM, action="store", help="Charm file to be deployed")
    parser.addoption(FLASK_APP_IMAGE_PARAM, action="store", help="Flask app image to be deployed")
    parser.addoption(
        USE_EXISTING_APP_PARAM,
        action="store_true",
        help="Use an existing app instead of deploying a new one, useful for local testing",
    )
    parser.addoption(
        GITHUB_TOKEN_PARAM,
        action="store",
        help="GitHub token used for testing github API interactions",
    )
    parser.addoption(
        GITHUB_APP_CLIENT_ID_PARAM,
        action="store",
        help="GitHub App ID used for testing github API interactions",
    )
    parser.addoption(
        GITHUB_APP_INSTALLATION_ID_PARAM_NAME,
        action="store",
        help="GitHub App installation ID used for testing github API interactions",
    )
    parser.addoption(
        GITHUB_APP_PRIVATE_KEY_PARAM_NAME,
        action="store",
        help="GitHub App private key used for testing github API interactions",
    )
    parser.addoption(
        WEBHOOK_TEST_REPOSITORY_PARAM,
        action="store",
        help="Name of the GitHub repository used to test webhook delivery",
        default="canonical/github-runner-webhook-router",
    )
