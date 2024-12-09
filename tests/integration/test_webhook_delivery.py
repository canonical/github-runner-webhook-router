#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
from asyncio import sleep
from typing import Iterator
from uuid import uuid4

import pytest
from github import Github, Hook, Repository
from github.Auth import Token
from juju.action import Action
from juju.application import Application
from juju.model import Model
from juju.unit import Unit

@pytest.fixture(name="repo", scope="module")
def repo_fixture(github_token: str, test_repo: str) -> Repository:
    github = Github(auth=Token(github_token))
    repo = github.get_repo(test_repo)

    return repo

@pytest.fixture(name="hook", scope="module")
def hook_fixture(github_token: str, repo: Repository) -> Iterator["Hook"]:
    unique_url = f"http://192.168.0.1:8080/{uuid4().hex}" # we need a unique url to distinguish this webhook from others, the ip is internal and the webhook delivery is expected to fail
    hook = repo.create_hook(name="web", events=["workflow_job"], config={"url": unique_url, "content_type":"json","insecure_ssl":"0"})

    yield hook

    hook.delete()


async def test_webhook_delivery(router: Application, github_token: str, repo: Repository, hook: Hook) -> None:
    unit: Unit = router.units[0]
    # create secret with github token
    model: Model = router.model
    secret_name = f"github-token-{uuid4().hex}" # use uuid in case same model is reused
    secret = await model.add_secret(secret_name, [f"token={github_token}"])
    secret_id = secret.split(":")[-1]
    await model.grant_secret(secret_name, router.name)
    # create webhook
    # trigger run
    assert repo.get_workflow("dispatch_test.yaml").create_dispatch(ref="main")

    # confirm webhook delivery failed
    async def wait_for_webhook_delivery(event: str) -> None:
        for _ in range(10):
            deliveries = repo.get_hook_deliveries(hook.id)
            for d in deliveries:
                if d.event == event:
                    return
            await sleep(1)
        assert False, f"Did not receive a webhook with event {event}"
    await wait_for_webhook_delivery("workflow_job")
    # call redliver webhook action
    action: Action = await unit.run_action("redeliver-failed-webhooks", **{"github-token-secret-id": secret_id, "webhook-id": hook.id, "since": 600, "github-path": repo.full_name})
    await action.wait()
    assert action.status == "completed"
    assert action.results.get("redelivered") == "1", f"redelivered not matching in {action.results}"

    async def wait_for_webhook_redelivered(event: str) -> None:
        for _ in range(10):
            deliveries = repo.get_hook_deliveries(hook.id)
            for d in deliveries:
                if d.event == event and d.redelivery:
                    return
            await sleep(1)
        assert False, f"Did not receive a redelivered webhook with event {event}"

    await wait_for_webhook_redelivered("workflow_job")

# @pytest.mark.parametrize(
#         "github_app_id, github_app_installation_id, github_app_private_key_secret_id, github_token_secret_id,"
#         "expected_message",
#         [
#             pytest.param(
#                 "123",
#                 "456",
#                 "private",
#                 secrets.token_hex(16),
#                 "Provided github app auth parameters and github token, only one of them should be provided",
#                 id="github app config and github token secret",
#             ),
#             pytest.param(
#                 None,
#                 None,
#                 None,
#                 None,
#                 "Either the github-token-secret-id or not all of github-app-id, github-app-installation-id, ",
#                 id="no github app config or github token",
#             ),
#             pytest.param(
#                 "eda",
#                 "no int",
#                 "private",
#                 None,
#                 "Invalid github app installation id",
#                 id="invalid github app installation id",
#             ),
#             pytest.param(
#                 "eda",
#                 "123",
#                 None,
#                 None,
#                 "Not all github app config provided",
#                 id="not all github app config provided",
#             ),
#         ],
#     )  # we use a lot of arguments, but it seems not worth to introduce a capsulating object for this
#     def test_get_client_configuration_error(  # pylint: disable=too-many-arguments
#             github_app_id: str,
#             github_app_installation_id: str,
#             github_app_private_key_secret_id: str,
#             github_token_secret_id: str,
#             expected_message: str,
#             monkeypatch: pytest.MonkeyPatch,
#     ):
#         """
#         arrange: Given a mocked environment with invalid github auth configuration.
#         act: Call github_client.get.
#         assert: ConfigurationError is raised.
#         """
#         harness = Harness(FlaskCharm)
#         harness.begin_with_initial_hooks()
#
#         event = MagicMock(spec=ActionEvent)
#         event.params = {
#             GITHUB_APP_ID_PARAM_NAME: github_app_id,
#             GITHUB_APP_INSTALLATION_ID_PARAM_NAME: github_app_installation_id,
#             GITHUB_APP_PRIVATE_KEY_SECRET_ID_PARAM_NAME: github_app_private_key_secret_id,
#             GITHUB_TOKEN_SECRET_ID_PARAM_NAME: github_token_secret_id,
#         }
#         result = harness.charm.on.redeliver_failed_webhooks_action(event)
#
#         assert expected_message in result
#         event.set_results.assert_not_called()