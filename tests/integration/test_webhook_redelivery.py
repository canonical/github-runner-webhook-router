#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
"""Integration tests for the webhook redelivery script."""

import secrets
from asyncio import sleep
from datetime import datetime, timezone
from typing import Callable, Iterator
from uuid import uuid4

import pytest
from github import Github
from github.Auth import Token
from github.Hook import Hook
from github.HookDelivery import HookDeliverySummary
from github.Repository import Repository
from github.Workflow import Workflow
from juju.action import Action
from juju.application import Application
from juju.unit import Unit

from tests.integration.conftest import GithubAuthenticationMethodParams

# some tests do not require real gh resources, so we use fake values for them in those tests
FAKE_HOOK_ID = 123
FAKE_REPO = "org/repo"

# this is no hardcoded password
GITHUB_APP_PRIVATE_KEY_SECRET_ID_PARAM_NAME = "github-app-private-key-secret-id"  # nosec
GITHUB_APP_CLIENT_ID_PARAM_NAME = "github-app-client-id"
GITHUB_APP_INSTALLATION_ID_PARAM_NAME = "github-app-installation-id"
GITHUB_TOKEN_SECRET_ID_PARAM_NAME = "github-token-secret-id"  # nosec this is no hardcoded password

TEST_WORKFLOW_DISPATCH_FILE = "webhook_redelivery_test.yaml"


@pytest.fixture(name="repo", scope="module")
def repo_fixture(github_token: str, test_repo: str) -> Repository:
    """Create a repository object for the test repo."""
    github = Github(auth=Token(github_token))
    repo = github.get_repo(test_repo)

    return repo


@pytest.fixture(name="hook")
def hook_fixture(repo: Repository) -> Iterator["Hook"]:
    """Create a webhook for the test repo.

    The hook gets deleted after the test.
    """
    # we need a unique url to distinguish this webhook from others
    # the ip is internal and the webhook delivery is expected to fail
    unique_url = f"http://192.168.0.1:8080/{uuid4().hex}"
    hook = repo.create_hook(
        name="web",
        events=["workflow_job"],
        config={"url": unique_url, "content_type": "json", "insecure_ssl": "0"},
    )

    yield hook

    hook.delete()


@pytest.fixture(name="test_workflow", scope="module")
def test_workflow_fixture(repo: Repository) -> Iterator[Workflow]:
    """Create a workflow for the test repo."""
    start_time = datetime.now(timezone.utc)
    workflow = repo.get_workflow(TEST_WORKFLOW_DISPATCH_FILE)
    yield workflow
    # cancel all runs, it's not necessary to stay in queue or be picked up by a runner
    for run in workflow.get_runs(created=f">={start_time.isoformat()}"):
        run.cancel()


async def test_webhook_redelivery(
    router: Application,
    github_auth: GithubAuthenticationMethodParams,
    repo: Repository,
    hook: Hook,
    test_workflow: Workflow,
) -> None:
    """
    arrange: a hook with a failed delivery
    act: call the action to redeliver the webhook
    assert: the failed delivery has been redelivered
    """
    unit = router.units[0]

    action_parms = {"webhook-id": hook.id, "since": 600, "github-path": repo.full_name}
    secret_id = await _create_secret_for_github_auth(router, github_auth)
    if github_auth.token:
        action_parms["github-token-secret-id"] = secret_id
    else:
        action_parms |= {
            GITHUB_APP_PRIVATE_KEY_SECRET_ID_PARAM_NAME: secret_id,
            GITHUB_APP_CLIENT_ID_PARAM_NAME: github_auth.client_id,
            GITHUB_APP_INSTALLATION_ID_PARAM_NAME: github_auth.installation_id,
        }
    # we need to dispatch a job in order to have a webhook delivery with event "workflow_job"
    assert test_workflow.create_dispatch(ref="main")

    async def _wait_for_delivery_condition(
        condition: Callable[[HookDeliverySummary], bool], condition_title: str
    ) -> None:
        """Wait to find a certain delivery with the condition."""
        for _ in range(10):
            deliveries = repo.get_hook_deliveries(hook.id)
            for delivery in deliveries:
                if condition(delivery):
                    return
            await sleep(1)
        assert False, f"Did not receive a webhook who fits the condition '{condition_title}'"

    await _wait_for_delivery_condition(
        lambda d: d.event == "workflow_job", "event is workflow_job"
    )

    action: Action = await unit.run_action("redeliver-failed-webhooks", **action_parms)

    await action.wait()
    assert action.status == "completed", f"action failed with f{action.data['message']}"
    assert (
        action.results.get("redelivered") == "1"
    ), f"redelivered not matching in {action.results}"
    await _wait_for_delivery_condition(
        lambda d: d.event == "workflow_job" and bool(d.redelivery),
        "delivery with event workflow_job has been redelivered",
    )


@pytest.mark.parametrize(
    "github_app_client_id, github_app_installation_id, "
    "github_app_private_key_secret, github_token_secret,"
    "expected_message",
    [
        pytest.param(
            "123",
            446,
            "private",
            "token",
            "Github auth details are specified in two ways. "
            "Please specify only one of github token or github app auth details.",
            id="github app config and github token secret",
        ),
        pytest.param(
            None,
            None,
            None,
            None,
            "Github auth details are not specified completely."
            " Am missing github token or complete set of app auth parameters.",
            id="no github app config or github token",
        ),
        pytest.param(
            "eda",
            123,
            None,
            None,
            "Github auth details are not specified completely."
            " Am missing github token or complete set of app auth parameters.",
            id="not all github app config provided",
        ),
    ],
)  # we use a lot of arguments, but it seems not worth to introduce a capsulating object for this
async def test_action_github_auth_param_error(
    # pylint: disable=too-many-arguments,too-many-positional-arguments
    github_app_client_id: str | None,
    github_app_installation_id: int | None,
    github_app_private_key_secret: str | None,
    github_token_secret: str | None,
    expected_message: str,
    router: Application,
):
    """
    arrange: Given a mocked environment with invalid github auth configuration.
    act: Call the action.
    assert: The action fails with the expected message.
    """
    unit: Unit = router.units[0]

    secret_data = []
    action_parms = {"webhook-id": FAKE_HOOK_ID, "since": 600, "github-path": FAKE_REPO}
    if github_app_private_key_secret:
        secret_data.append(f"private-key={github_app_private_key_secret}")
    if github_token_secret:
        secret_data.append(f"token={github_token_secret}")
    if secret_data:
        secret_id = await _create_secret(router, secret_data)
        if github_app_private_key_secret:
            action_parms[GITHUB_APP_PRIVATE_KEY_SECRET_ID_PARAM_NAME] = secret_id
        if github_token_secret:
            action_parms[GITHUB_TOKEN_SECRET_ID_PARAM_NAME] = secret_id
    if github_app_client_id:
        action_parms[GITHUB_APP_CLIENT_ID_PARAM_NAME] = github_app_client_id
    if github_app_installation_id:
        action_parms[GITHUB_APP_INSTALLATION_ID_PARAM_NAME] = github_app_installation_id

    action: Action = await unit.run_action("redeliver-failed-webhooks", **action_parms)
    await action.wait()

    assert action.status == "failed"
    assert "Argument parsing failed" in (action_msg := action.data["message"])
    assert expected_message in action_msg


@pytest.mark.parametrize(
    "use_app_auth",
    [
        pytest.param(
            True,
            id="wrong field in github app secret",
        ),
        pytest.param(
            False,
            id="wrong field in github token secret",
        ),
    ],
)
async def test_secret_missing(use_app_auth: bool, router: Application) -> None:
    """
    arrange: Given auth parameters with a secret which is missing.
    act: Call the action.
    assert: The action fails with the expected message.
    """
    unit: Unit = router.units[0]

    action_parms = {"webhook-id": FAKE_HOOK_ID, "since": 600, "github-path": FAKE_REPO}
    if use_app_auth:
        action_parms |= {
            GITHUB_APP_PRIVATE_KEY_SECRET_ID_PARAM_NAME: secrets.token_hex(16),
            GITHUB_APP_CLIENT_ID_PARAM_NAME: secrets.token_hex(16),
            GITHUB_APP_INSTALLATION_ID_PARAM_NAME: 123,
        }
    else:
        action_parms["github-token-secret-id"] = secrets.token_hex(16)

    action: Action = await unit.run_action("redeliver-failed-webhooks", **action_parms)

    await action.wait()
    assert action.status == "failed"
    assert "Invalid action parameters passed" in (action_msg := action.data["message"])
    assert "Could not access/find secret" in action_msg


@pytest.mark.parametrize(
    "use_app_auth, expected_message",
    [
        pytest.param(
            True,
            "does not contain a field called 'private-key'.",
            id="wrong field in github app secret",
        ),
        pytest.param(
            False,
            "does not contain a field called 'token'.",
            id="wrong field in github token secret",
        ),
    ],
)
async def test_secret_key_missing(
    use_app_auth: bool, expected_message: str, router: Application
) -> None:
    """
    arrange: Given auth parameters with a secret which is missing a key.
    act: Call the action.
    assert: The action fails with the expected message.
    """
    unit = router.units[0]

    action_parms = {"webhook-id": FAKE_HOOK_ID, "since": 600, "github-path": FAKE_REPO}
    secret_data = [
        f"private-key-invalid={secrets.token_hex(16)}",
        f"token-invalid={secrets.token_hex(16)}",
    ]
    secret_id = await _create_secret(router, secret_data)
    if use_app_auth:
        action_parms |= {
            GITHUB_APP_PRIVATE_KEY_SECRET_ID_PARAM_NAME: secret_id,
            GITHUB_APP_CLIENT_ID_PARAM_NAME: secrets.token_hex(16),
            GITHUB_APP_INSTALLATION_ID_PARAM_NAME: 123,
        }
    else:
        action_parms["github-token-secret-id"] = secret_id

    action: Action = await unit.run_action("redeliver-failed-webhooks", **action_parms)
    await action.wait()

    assert action.status == "failed"
    assert "Invalid action parameters passed" in (action_msg := action.data["message"])
    assert expected_message in action_msg


async def _create_secret_for_github_auth(
    app: Application, github_auth: GithubAuthenticationMethodParams
) -> str:
    """Create a secret with appropriate key depending on the Github auth type."""
    if github_auth.token:
        secret_data = [f"token={github_auth.token}"]
    else:
        secret_data = [f"private-key={github_auth.private_key}"]

    return await _create_secret(app, secret_data)


async def _create_secret(app: Application, secret_data: list[str]) -> str:
    """Create a secret with the given data."""
    secret_name = f"secret-{uuid4().hex}"
    secret = await app.model.add_secret(secret_name, secret_data)
    secret_id = secret.split(":")[-1]

    await app.model.grant_secret(secret_name, app.name)

    return secret_id
