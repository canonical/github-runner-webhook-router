#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
import secrets
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

import github
import pytest
from github.HookDelivery import HookDeliverySummary

from webhook_redelivery import redeliver_failed_webhook_deliveries, GithubAuthDetails, \
    WebhookAddress, _WebhookDelivery


def test_redeliver(monkeypatch: pytest.MonkeyPatch):
    github_client = MagicMock(spec=github.Github)
    monkeypatch.setattr("webhook_redelivery._get_github_client", MagicMock(return_value=github_client))
    get_deliveries_mock = MagicMock()
    monkeypatch.setattr("webhook_redelivery._get_deliveries", get_deliveries_mock)
    redeliver_mock = MagicMock()
    monkeypatch.setattr("webhook_redelivery._redeliver", redeliver_mock)


    now = datetime.now(tz=timezone.utc)

    monkeypatch.setattr("webhook_redelivery.datetime", MagicMock(now=MagicMock(return_value=now)))

    get_deliveries_mock.return_value = [
        _WebhookDelivery(delivery_id=i, status="failed", delivered_at=now - timedelta(seconds=i))
        for i in range(1, 11)
    ]

    github_token = secrets.token_hex(16)
    webhook_address = WebhookAddress(github_org=secrets.token_hex(16), github_repo=secrets.token_hex(16), id=1234)
    redelivered = redeliver_failed_webhook_deliveries(github_auth=github_token, webhook_address=webhook_address, since_seconds=5)

    assert redelivered == 5
    assert redeliver_mock.call_count == 5
    for i in range(1, 6):
        redeliver_mock.assert_any_call(github_client=github_client, webhook_address=webhook_address, delivery_id=i)
