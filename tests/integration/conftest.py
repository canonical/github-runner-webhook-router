#  Copyright 2026 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Fixtures for the github-runner-webhook-router charm."""

import os
import random
from collections import namedtuple
from typing import Any

import pytest
import pytest_asyncio
from juju.application import Application
from juju.model import Model
from pytest_operator.plugin import OpsTest

from tests.conftest import (
    CHARM_FILE_PARAM,
    FLASK_APP_IMAGE_PARAM,
    GITHUB_APP_CLIENT_ID_PARAM,
    GITHUB_APP_INSTALLATION_ID_PARAM_NAME,
    GITHUB_APP_PRIVATE_KEY_PARAM_NAME,
    GITHUB_TOKEN_PARAM,
    WEBHOOK_TEST_REPOSITORY_PARAM,
)

GITHUB_TOKEN_ENV_VAR = "GITHUB_TOKEN"  # nosec this is no hardcoded password
GITHUB_APP_INSTALLATION_ID_ENV_VAR = "GITHUB_APP_INSTALLATION_ID"
GITHUB_APP_PRIVATE_KEY_ENV_VAR = "GITHUB_APP_PRIVATE_KEY"
GITHUB_APP_CLIENT_ID_ENV_VAR = "GITHUB_APP_CLIENT_ID"

GithubAuthenticationMethodParams = namedtuple(
    "GithubAuthenticationMethodParams", ["client_id", "installation_id", "private_key", "token"]
)


@pytest.fixture(name="use_existing_app", scope="module")
def use_existing_app_fixture(pytestconfig: pytest.Config) -> bool:
    """Return whether to use an existing app instead of deploying a new one."""
    return pytestconfig.getoption("--use-existing-app")


@pytest.fixture(name="charm_file", scope="module")
def charm_file_fixture(pytestconfig: pytest.Config) -> str | None:
    """Return the path to the built charm file."""
    charm = pytestconfig.getoption(CHARM_FILE_PARAM)
    return charm


@pytest.fixture(name="flask_app_image", scope="module")
def flask_app_image_fixture(pytestconfig: pytest.Config) -> str | None:
    """Return the path to the flask app image"""
    flask_app_image = pytestconfig.getoption(FLASK_APP_IMAGE_PARAM)
    return flask_app_image


@pytest.fixture(name="github_token", scope="module")
def github_token_fixture(pytestconfig: pytest.Config) -> str | None:
    """Return the github token secret"""
    github_token = pytestconfig.getoption(GITHUB_TOKEN_PARAM) or os.getenv(GITHUB_TOKEN_ENV_VAR)
    return github_token


@pytest.fixture(name="github_app_client_id", scope="module")
def github_app_client_id_fixture(pytestconfig: pytest.Config) -> str | None:
    """Return the github app id"""
    github_app_client_id = pytestconfig.getoption(GITHUB_APP_CLIENT_ID_PARAM) or os.getenv(
        GITHUB_APP_CLIENT_ID_ENV_VAR
    )
    return github_app_client_id


@pytest.fixture(name="github_app_installation_id", scope="module")
def github_app_installation_id_fixture(pytestconfig: pytest.Config) -> int | None:
    """Return the github app installation id"""
    github_app_installation_id = pytestconfig.getoption(
        GITHUB_APP_INSTALLATION_ID_PARAM_NAME
    ) or os.getenv(GITHUB_APP_INSTALLATION_ID_ENV_VAR)
    if github_app_installation_id is None:
        return None
    return int(github_app_installation_id)


@pytest.fixture(name="github_app_private_key", scope="module")
def github_app_private_key_fixture(pytestconfig: pytest.Config) -> str | None:
    """Return the github app private key"""
    github_app_private_key = pytestconfig.getoption(
        GITHUB_APP_PRIVATE_KEY_PARAM_NAME
    ) or os.getenv(GITHUB_APP_PRIVATE_KEY_ENV_VAR)
    return github_app_private_key


@pytest.fixture(
    name="github_auth",
    scope="module",
    params=[
        pytest.param(True, id="use github token"),
        pytest.param(False, id="use github app auth"),
    ],
)
def github_auth_fixture(
    request: pytest.FixtureRequest,
    github_token: str | None,
    github_app_client_id: str | None,
    github_app_installation_id: str | None,
    github_app_private_key: str | None,
) -> GithubAuthenticationMethodParams:
    """Return whether to use github app auth"""
    if request.param:
        assert github_token is not None, "Github token is required"
        return GithubAuthenticationMethodParams(
            client_id=None, installation_id=None, private_key=None, token=github_token
        )
    if not (github_app_client_id or github_app_installation_id or github_app_private_key):
        pytest.skip("Not all github app auth parameters provided/non-empty")
    return GithubAuthenticationMethodParams(
        client_id=github_app_client_id,
        installation_id=github_app_installation_id,
        private_key=github_app_private_key,
        token=None,
    )


@pytest.fixture(name="test_repo", scope="module")
def test_repo_fixture(pytestconfig: pytest.Config) -> str | None:
    """Return the github test repository"""
    test_repo = pytestconfig.getoption(WEBHOOK_TEST_REPOSITORY_PARAM)
    return test_repo


@pytest.fixture(name="model", scope="module")
def model_fixture(ops_test: OpsTest) -> Model:
    """Juju model used in the test."""
    assert ops_test.model is not None
    return ops_test.model


@pytest.fixture(name="app_name", scope="module")
def app_name_fixture() -> str:
    """Application name."""
    return "github-runner-webhook-router"


@pytest.fixture(name="worker_count", scope="module")
def worker_count_fixture() -> int:
    """Return the number of worker processes to use for gunicorn."""
    # We do not use randint for cryptographic purposes.
    return random.randint(1, 5)  # nosec


@pytest_asyncio.fixture(name="mongodb", scope="module")
async def mongodb_fixture(model: Model, use_existing_app: bool) -> Application:
    """Deploy the mongodb application."""
    if use_existing_app:
        application = model.applications["mongodb"]
    else:
        application = await model.deploy(
            "mongodb-k8s",
            channel="6/edge",
            application_name="mongodb",
            trust=True,
        )

    await model.wait_for_idle(apps=[application.name], status="active")
    return application


@pytest.fixture(name="deploy_config", scope="module")
def deploy_config_fixture(
    charm_file: str | None,
    flask_app_image: str | None,
    app_name: str,
    worker_count: int,
    use_existing_app: bool,
) -> dict[str, Any]:
    """Return the config required to deploy the charm."""
    return {
        "charm-file": charm_file,
        "flask-app-image": flask_app_image,
        "config": {
            "webserver-workers": worker_count,
            "flavours": '- small: ["small"]',
            "default-flavour": "small",
        },
        "app-name": app_name,
        "use-existing-app": use_existing_app,
    }


@pytest_asyncio.fixture(name="router", scope="module")
async def router_fixture(
    model: Model,
    deploy_config: dict[str, Any],
) -> Application:
    """Deploy the application."""
    app_name = deploy_config["app-name"]
    if deploy_config["use-existing-app"]:
        application = model.applications[app_name]
    else:
        charm_file = deploy_config["charm-file"]
        flask_app_image = deploy_config["flask-app-image"]
        assert charm_file is not None, "Charm file is required"
        assert flask_app_image is not None, "Flask app image is required"
        resources = {
            "flask-app-image": flask_app_image,
        }

        application = await model.deploy(
            charm_file,
            resources=resources,
            application_name=deploy_config["app-name"],
            config=deploy_config["config"],
        )
        await model.wait_for_idle(apps=[app_name], status="blocked")
    return application
