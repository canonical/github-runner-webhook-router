#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Unit tests for webhook redelivery script."""
import secrets
from collections import namedtuple
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import github
import pytest
from github.HookDelivery import HookDeliverySummary

from webhook_redelivery import (
    OK_STATUS,
    RedeliveryError,
    WebhookAddress,
    _redeliver_failed_webhook_delivery_attempts,
)

_Delivery = namedtuple("_Delivery", ["id", "status", "age"])


@pytest.fixture(
    name="webhook_address",
    params=[
        pytest.param(True, id="repository webhook"),
        pytest.param(False, id="organization webhook"),
    ],
)
def webhook_address_fixture(request: pytest.FixtureRequest) -> WebhookAddress:
    """Return a webhook address for a repository and for an organization."""
    return WebhookAddress(
        github_org=secrets.token_hex(16),
        github_repo=secrets.token_hex(16) if request.param else None,
        id=1234,
    )


@pytest.mark.parametrize(
    "deliveries,since_seconds,expected_redelivered",
    [
        pytest.param([], 5, set(), id="empty"),
        pytest.param([_Delivery(1, "failed", 4)], 5, {1}, id="one failed"),
        pytest.param([_Delivery(1, "failed", 4)], 3, set(), id="one failed but too old"),
        pytest.param([_Delivery(1, "failed", 1)], 0, {}, id="one failed zero since seconds"),
        pytest.param([_Delivery(1, "failed", 0)], 0, {1}, id="one failed zero age"),
        pytest.param(
            [_Delivery(1, "failed", 0)], -1, {}, id="one failed zero age negative since seconds"
        ),
        pytest.param(
            [_Delivery(1, "failed", 4), _Delivery(2, "failed", 4)], 5, {1, 2}, id="two failed"
        ),
        pytest.param([_Delivery(1, OK_STATUS, 4)], 5, set(), id="one OK"),
        pytest.param(
            [_Delivery(1, OK_STATUS, 3), _Delivery(2, OK_STATUS, 3), _Delivery(3, "failed", 4)],
            5,
            {3},
            id="two OK one failed",
        ),
        pytest.param(
            [_Delivery(1, OK_STATUS, 3), _Delivery(2, OK_STATUS, 3), _Delivery(3, "failed", 4)],
            2,
            set(),
            id="two OK one failed but too old",
        ),
        pytest.param(
            [
                _Delivery(1, OK_STATUS, 3),
                _Delivery(2, OK_STATUS, 3),
                _Delivery(3, "failed", 4),
                _Delivery(4, "failed", 3),
            ],
            1,
            {},
            id="two OK two failed and all too old",
        ),
    ],
)
def test_redeliver(
    monkeypatch: pytest.MonkeyPatch,
    deliveries: list[_Delivery],
    since_seconds: int,
    expected_redelivered: set[int],
    webhook_address: WebhookAddress,
):
    github_client = MagicMock(spec=github.Github)
    monkeypatch.setattr("webhook_redelivery.Github", MagicMock(return_value=github_client))
    now = datetime.now(tz=timezone.utc)
    monkeypatch.setattr("webhook_redelivery.datetime", MagicMock(now=MagicMock(return_value=now)))

    get_hook_deliveries_mock = _get_get_deliveries_mock(github_client, webhook_address)
    get_hook_deliveries_mock.return_value = [
        MagicMock(
            spec=HookDeliverySummary,
            id=d.id,
            status=d.status,
            action="queued",
            event="workflow_job",
            delivered_at=now - timedelta(seconds=d.age),
        )
        for d in deliveries
    ]

    github_token = secrets.token_hex(16)
    redelivered = _redeliver_failed_webhook_delivery_attempts(
        github_auth=github_token, webhook_address=webhook_address, since_seconds=since_seconds
    )

    assert redelivered == len(expected_redelivered)

    redeliver_mock = github_client.requester.requestJsonAndCheck
    assert redeliver_mock.call_count == redelivered
    for _id in expected_redelivered:
        return redeliver_mock.assert_any_call(
            "POST", _get_redeliver_mock_api_url(webhook_address, _id)
        )


@pytest.mark.parametrize(
    "github_exception,expected_msg",
    [
        pytest.param(
            github.BadCredentialsException(403),
            "The github client returned a Bad Credential error",
            id="BadCredentialsException",
        ),
        pytest.param(
            github.RateLimitExceededException(403),
            "The github client is returning a Rate Limit Exceeded error",
            id="RateLimitExceededException",
        ),
        pytest.param(
            github.GithubException(500),
            "The github client encountered an error",
            id="GithubException",
        ),
    ],
)
def test_redelivery_github_errors(
    monkeypatch: pytest.MonkeyPatch,
    github_exception: github.GithubException,
    expected_msg: str,
    webhook_address: WebhookAddress,
):
    github_client = MagicMock(spec=github.Github)
    monkeypatch.setattr("webhook_redelivery.Github", MagicMock(return_value=github_client))

    github_token = secrets.token_hex(16)
    since_seconds = 5

    get_hook_deliveries_mock = _get_get_deliveries_mock(github_client, webhook_address)
    get_hook_deliveries_mock.side_effect = github_exception

    with pytest.raises(RedeliveryError) as exc_info:
        _redeliver_failed_webhook_delivery_attempts(
            github_auth=github_token, webhook_address=webhook_address, since_seconds=since_seconds
        )
    assert expected_msg in str(exc_info.value)


@pytest.mark.parametrize(
    "action,event",
    [
        pytest.param("completed", "workflow_job", id="completed workflow_job"),
        pytest.param("in_progress", "workflow_job", id="in_progress workflow_job"),
        pytest.param("waiting", "workflow_job", id="waiting workflow_job"),
        pytest.param("queued", "push", id="queued push"),
        pytest.param("completed", "push", id="completed push"),
        pytest.param("queued", "workflow_run", id="queued workflow_run"),
    ],
)
def test_redelivery_ignores_non_queued_or_non_workflow_job(
    monkeypatch: pytest.MonkeyPatch,
    webhook_address: WebhookAddress,
    action: str,
    event: str,
):
    github_client = MagicMock(spec=github.Github)
    monkeypatch.setattr("webhook_redelivery.Github", MagicMock(return_value=github_client))
    now = datetime.now(tz=timezone.utc)
    monkeypatch.setattr("webhook_redelivery.datetime", MagicMock(now=MagicMock(return_value=now)))

    get_hook_deliveries_mock = _get_get_deliveries_mock(github_client, webhook_address)
    get_hook_deliveries_mock.return_value = [
        MagicMock(
            spec=HookDeliverySummary,
            id=d.id,
            status=d.status,
            action=action,
            event=event,
            delivered_at=now - timedelta(seconds=d.age),
        )
        for d in [_Delivery(i, action, 4) for i in range(3)]
    ]

    github_token = secrets.token_hex(16)
    redelivered = _redeliver_failed_webhook_delivery_attempts(
        github_auth=github_token, webhook_address=webhook_address, since_seconds=5
    )

    assert redelivered == 0

    redeliver_mock = github_client.requester.requestJsonAndCheck
    assert redeliver_mock.call_count == 0


def _get_get_deliveries_mock(
    github_client_mock: MagicMock, webhook_address: WebhookAddress
) -> MagicMock:
    """Return the mock for the get_hook_deliveries method."""
    return (
        github_client_mock.get_repo.return_value.get_hook_deliveries
        if webhook_address.github_repo
        else github_client_mock.get_organization.return_value.get_hook_deliveries
    )


def _get_redeliver_mock_api_url(webhook_address: WebhookAddress, delivery_id: int) -> str:
    """Return the expected API URL for redelivering a webhook."""
    return (
        f"/repos/{webhook_address.github_org}/{webhook_address.github_repo}"
        f"/hooks/{webhook_address.id}/deliveries/{delivery_id}/attempts"
        if webhook_address.github_repo
        else f"/orgs/{webhook_address.github_org}/hooks/{webhook_address.id}"
        f"/deliveries/{delivery_id}/attempts"
    )
