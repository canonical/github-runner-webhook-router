# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for charm tests."""

from pytest import Parser

CHARM_FILE_PARAM = "--charm-file"
FLASK_APP_IMAGE_PARAM = "--github-runner-webhook-router-image"
USE_EXISTING_APP_PARAM = "--use-existing-app"


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
