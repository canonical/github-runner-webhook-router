#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import secrets
from collections import namedtuple
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import github
import pytest
from github.HookDelivery import HookDeliverySummary

from webhook_redelivery import OK_STATUS, WebhookAddress, redeliver_failed_webhook_deliveries

_Delivery = namedtuple("_Deliveries", ["id", "status", "age"])


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
):
    github_client = MagicMock(spec=github.Github)
    monkeypatch.setattr("webhook_redelivery.Github", MagicMock(return_value=github_client))
    now = datetime.now(tz=timezone.utc)
    monkeypatch.setattr("webhook_redelivery.datetime", MagicMock(now=MagicMock(return_value=now)))

    github_client.get_repo.return_value.get_hook_deliveries.return_value = [
        MagicMock(
            spec=HookDeliverySummary,
            id=d.id,
            status=d.status,
            delivered_at=now - timedelta(seconds=d.age),
        )
        for d in deliveries
    ]

    github_token = secrets.token_hex(16)
    webhook_address = WebhookAddress(
        github_org=secrets.token_hex(16), github_repo=secrets.token_hex(16), id=1234
    )
    redelivered = redeliver_failed_webhook_deliveries(
        github_auth=github_token, webhook_address=webhook_address, since_seconds=since_seconds
    )

    assert redelivered == len(expected_redelivered)

    redeliver_mock = github_client.requester.requestJsonAndCheck
    assert redeliver_mock.call_count == redelivered
    for _id in expected_redelivered:
        return redeliver_mock.assert_any_call(
            "POST",
            f"/repos/{webhook_address.github_org}/{webhook_address.github_repo}/hooks/{webhook_address.id}/deliveries/{_id}/attempts",
        )
