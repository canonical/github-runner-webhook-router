# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the github-runner-webhook-router charm's custom functionality."""

import json
import os
import pathlib
import sys

import pytest

CHARM_DIR = pathlib.Path(__file__).parents[2]
sys.path.insert(0, str(CHARM_DIR / "lib"))
sys.path.insert(0, str(CHARM_DIR / "src"))

from ops import testing  # noqa: E402

import charm  # noqa: E402

_REDELIVERY_SCRIPT = ["/usr/bin/python3", "/flask/app/webhook_redelivery.py"]


class TestGetCosDir:
    """Test the get_cos_dir method."""

    def test_returns_charm_src_dir(self):
        """get_cos_dir returns an absolute path."""
        ctx = testing.Context(charm.FlaskCharm)
        container = testing.Container("flask-app", can_connect=True)
        state = testing.State(containers={container}, leader=True)

        with ctx(ctx.on.start(), state) as mgr:
            cos_dir = mgr.charm.get_cos_dir()
            assert os.path.isabs(cos_dir)
            mgr.run()


class TestRedeliverFailedWebhooksAction:
    """Test the redeliver-failed-webhooks action."""

    def test_redeliver_with_token_auth(self):
        """Action with github-token-secret-id uses token authentication."""
        result_json = json.dumps({"redelivered": 5, "failed": 0})
        ctx = testing.Context(charm.FlaskCharm)
        secret = testing.Secret(
            tracked_content={"token": "ghp_testtoken123"},
            owner="app",
        )
        container = testing.Container(
            "flask-app",
            can_connect=True,
            execs={testing.Exec(_REDELIVERY_SCRIPT, stdout=result_json)},
        )
        state = testing.State(
            containers={container},
            leader=True,
            secrets={secret},
        )

        ctx.run(
            ctx.on.action(
                "redeliver-failed-webhooks",
                params={
                    "since": 3600,
                    "github-path": "canonical/test-repo",
                    "webhook-id": 12345,
                    "github-token-secret-id": secret.id,
                },
            ),
            state,
        )

        exec_record = ctx.exec_history["flask-app"][0]
        assert "/flask/app/webhook_redelivery.py" in exec_record.command
        assert "--since" in exec_record.command
        assert "3600" in exec_record.command
        assert "--github-path" in exec_record.command
        assert "canonical/test-repo" in exec_record.command
        assert exec_record.environment["GITHUB_TOKEN"] == "ghp_testtoken123"
        assert ctx.action_results == {"redelivered": 5, "failed": 0}

    def test_redeliver_fails_on_exec_error(self):
        """Action fails when the redelivery script returns non-zero."""
        ctx = testing.Context(charm.FlaskCharm)
        container = testing.Container(
            "flask-app",
            can_connect=True,
            execs={testing.Exec(_REDELIVERY_SCRIPT, return_code=2, stderr="Error processing webhooks")},
        )
        state = testing.State(containers={container}, leader=True)

        with pytest.raises(testing.ActionFailed):
            ctx.run(
                ctx.on.action(
                    "redeliver-failed-webhooks",
                    params={
                        "since": 3600,
                        "github-path": "canonical/test-repo",
                        "webhook-id": 12345,
                    },
                ),
                state,
            )

    def test_redeliver_arg_parse_error(self):
        """Action reports arg parse error when exit code is 1."""
        ctx = testing.Context(charm.FlaskCharm)
        container = testing.Container(
            "flask-app",
            can_connect=True,
            execs={testing.Exec(_REDELIVERY_SCRIPT, return_code=1, stderr="Invalid arguments")},
        )
        state = testing.State(containers={container}, leader=True)

        with pytest.raises(testing.ActionFailed) as exc_info:
            ctx.run(
                ctx.on.action(
                    "redeliver-failed-webhooks",
                    params={
                        "since": 3600,
                        "github-path": "canonical/test-repo",
                        "webhook-id": 12345,
                    },
                ),
                state,
            )

        assert "Argument parsing failed" in exc_info.value.message

    def test_redeliver_with_github_app_auth(self):
        """Action with github-app params uses app authentication."""
        result_json = json.dumps({"redelivered": 2, "failed": 1})
        ctx = testing.Context(charm.FlaskCharm)
        pk_secret = testing.Secret(
            tracked_content={"private-key": "-----BEGIN RSA PRIVATE KEY-----\nfoo"},
            owner="app",
        )
        container = testing.Container(
            "flask-app",
            can_connect=True,
            execs={testing.Exec(_REDELIVERY_SCRIPT, stdout=result_json)},
        )
        state = testing.State(
            containers={container},
            leader=True,
            secrets={pk_secret},
        )

        ctx.run(
            ctx.on.action(
                "redeliver-failed-webhooks",
                params={
                    "since": 1800,
                    "github-path": "canonical",
                    "webhook-id": 999,
                    "github-app-client-id": "Iv1.abc123",
                    "github-app-installation-id": 42,
                    "github-app-private-key-secret-id": pk_secret.id,
                },
            ),
            state,
        )

        env = ctx.exec_history["flask-app"][0].environment
        assert env["GITHUB_APP_CLIENT_ID"] == "Iv1.abc123"
        assert env["GITHUB_APP_INSTALLATION_ID"] == "42"
        assert "BEGIN RSA PRIVATE KEY" in env["GITHUB_APP_PRIVATE_KEY"]

    def test_redeliver_invalid_secret_fails(self):
        """Action fails when secret cannot be accessed."""
        ctx = testing.Context(charm.FlaskCharm)
        container = testing.Container("flask-app", can_connect=True)
        state = testing.State(containers={container}, leader=True)

        with pytest.raises(testing.ActionFailed) as exc_info:
            ctx.run(
                ctx.on.action(
                    "redeliver-failed-webhooks",
                    params={
                        "since": 3600,
                        "github-path": "canonical/test",
                        "webhook-id": 123,
                        "github-token-secret-id": "secret:nonexistent",
                    },
                ),
                state,
            )

        assert "Invalid action parameters" in exc_info.value.message
