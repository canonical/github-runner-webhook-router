#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import secrets
from asyncio import sleep
from datetime import datetime, timezone
from typing import Iterator
from uuid import uuid4

import pytest
from github import Github
from github.Auth import Token
from github.Hook import Hook
from github.Repository import Repository
from github.Workflow import Workflow
from juju.action import Action
from juju.application import Application
from juju.model import Model
from juju.unit import Unit

from tests.integration.conftest import GithubAuthenticationMethodParams

# some tests do not require real gh resources, so we use fake values for them in those tests
FAKE_HOOK_ID = 123
FAKE_REPO = "org/repo"

GITHUB_APP_PRIVATE_KEY_SECRET_ID_PARAM_NAME = "github-app-private-key-secret-id"
GITHUB_APP_CLIENT_ID_PARAM_NAME = "github-app-client-id"
GITHUB_APP_INSTALLATION_ID_PARAM_NAME = "github-app-installation-id"
GITHUB_TOKEN_SECRET_ID_PARAM_NAME = "github-token-secret-id"

TEST_WORKFLOW_DISPATCH_FILE = "webhook_redelivery_test.yaml"


@pytest.fixture(name="repo", scope="module")
def repo_fixture(github_token: str, test_repo: str) -> Repository:
    github = Github(auth=Token(github_token))
    repo = github.get_repo(test_repo)

    return repo


@pytest.fixture(name="hook")
def hook_fixture(github_token: str, repo: Repository) -> Iterator["Hook"]:
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
    start_time = datetime.now(timezone.utc)
    workflow = repo.get_workflow(TEST_WORKFLOW_DISPATCH_FILE)
    yield workflow
    # cancel all runs, it's not necessary to stay in queue or be picked up by a runner
    for run in workflow.get_runs(created=f">={start_time.isoformat()}"):
        run.cancel()


async def test_webhook_delivery(
    router: Application,
    github_app_auth: GithubAuthenticationMethodParams,
    repo: Repository,
    hook: Hook,
    test_workflow: Workflow,
) -> None:
    unit: Unit = router.units[0]
    # create secret with github token
    model: Model = router.model
    secret_name = f"github-auth-{uuid4().hex}"  # use uuid in case same model is reused

    action_parms = {"webhook-id": hook.id, "since": 600, "github-path": repo.full_name}
    if github_app_auth.token:
        secret = await model.add_secret(secret_name, [f"token={github_app_auth.token}"])
        secret_id = secret.split(":")[-1]
        action_parms["github-token-secret-id"] = secret_id
    else:
        secret = await model.add_secret(
            secret_name, [f"private-key={github_app_auth.private_key}"]
        )
        secret_id = secret.split(":")[-1]
        action_parms |= {
            GITHUB_APP_PRIVATE_KEY_SECRET_ID_PARAM_NAME: secret_id,
            GITHUB_APP_CLIENT_ID_PARAM_NAME: github_app_auth.client_id,
            GITHUB_APP_INSTALLATION_ID_PARAM_NAME: github_app_auth.installation_id,
        }
    await model.grant_secret(secret_name, router.name)

    assert test_workflow.create_dispatch(ref="main")

    # confirm webhook delivery failed
    async def _wait_for_webhook_delivery(event: str) -> None:
        """Wait for the webhook to be delivered."""
        for _ in range(10):
            deliveries = repo.get_hook_deliveries(hook.id)
            for d in deliveries:
                if d.event == event:
                    return
            await sleep(1)
        assert False, f"Did not receive a webhook with event {event}"

    await _wait_for_webhook_delivery("workflow_job")
    # call redliver webhook action
    action: Action = await unit.run_action("redeliver-failed-webhooks", **action_parms)
    await action.wait()
    assert action.status == "completed", f"action failed with f{action.data['message']}"
    assert (
        action.results.get("redelivered") == "1"
    ), f"redelivered not matching in {action.results}"

    async def _wait_for_webhook_redelivered(event: str) -> None:
        """Wait for the webhook to be redelivered."""
        for _ in range(10):
            deliveries = repo.get_hook_deliveries(hook.id)
            for d in deliveries:
                if d.event == event and d.redelivery:
                    return
            await sleep(1)
        assert False, f"Did not receive a redelivered webhook with event {event}"

    await _wait_for_webhook_redelivered("workflow_job")


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
            "Provided github app auth parameters and github token, "
            "only one of them should be provided",
            id="github app config and github token secret",
        ),
        pytest.param(
            None,
            None,
            None,
            None,
            "Either the github-token-secret-id or not all of github-app-id, "
            "github-app-installation-id, github-app-private-key-secret-id parameters were"
            " provided or are empty, the parameters are needed for interactions with GitHub",
            id="no github app config or github token",
        ),
        pytest.param(
            "eda",
            123,
            None,
            None,
            "Not all of github-app-id, github-app-installation-id, "
            "github-app-private-key-secret-id parameters were provided",
            id="not all github app config provided",
        ),
    ],
)  # we use a lot of arguments, but it seems not worth to introduce a capsulating object for this
async def test_action_github_auth_param_error(  # pylint: disable=too-many-arguments
    github_app_client_id: str | None,
    github_app_installation_id: int | None,
    github_app_private_key_secret: str | None,
    github_token_secret: str | None,
    expected_message: str,
    router: Application,
):
    """
    arrange: Given a mocked environment with invalid github auth configuration.
    act: Call github_client.get.
    assert: ConfigurationError is raised.
    """
    unit: Unit = router.units[0]
    # create secret with github token
    model: Model = router.model
    secret_name = f"github-creds-{uuid4().hex}"  # use uuid in case same model is reused
    secret_data = []
    action_parms = {"webhook-id": FAKE_HOOK_ID, "since": 600, "github-path": FAKE_REPO}
    if github_app_private_key_secret:
        secret_data.append(f"private-key={github_app_private_key_secret}")
    if github_token_secret:
        secret_data.append(f"token={github_token_secret}")
    if secret_data:
        secret = await model.add_secret(secret_name, secret_data)
        secret_id = secret.split(":")[-1]
        await model.grant_secret(secret_name, router.name)
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
    assert "Invalid action parameters passed" in (action_msg := action.data["message"])
    assert expected_message in action_msg


@pytest.mark.parametrize(
    "use_app_auth, expected_message",
    [
        pytest.param(
            True,
            "The github app private key secret does not contain a field called 'private-key'.",
            id="wrong field in github app secret",
        ),
        pytest.param(
            False,
            "The github token secret does not contain a field called 'token'.",
            id="wrong field in github token secret",
        ),
    ],
)
async def test_secret_key_missing(
    use_app_auth: bool, expected_message: str, router: Application
) -> None:
    unit: Unit = router.units[0]
    # create secret with github token
    model: Model = router.model
    secret_name = f"github-creds-{uuid4().hex}"  # use uuid in case same model is reused

    action_parms = {"webhook-id": FAKE_HOOK_ID, "since": 600, "github-path": FAKE_REPO}
    secret_data = [
        f"private-key-invalid={secrets.token_hex(16)}",
        f"token-invalid={secrets.token_hex(16)}",
    ]
    secret = await model.add_secret(secret_name, secret_data)
    secret_id = secret.split(":")[-1]
    await model.grant_secret(secret_name, router.name)
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
