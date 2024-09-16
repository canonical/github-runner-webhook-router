#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Unit tests for the parse module."""

import pytest

from webhook_router.parse import Job, JobStatus, ParseError, webhook_to_job

FAKE_JOB_URL = "https://api.github.com/repos/fakeusergh-runner-test/actions/jobs/8200803099"
FAKE_LABELS = ["self-hosted", "linux", "arm64"]


@pytest.mark.parametrize(
    "labels, status",
    [
        pytest.param(["self-hosted", "linux", "arm64"], JobStatus.QUEUED, id="self hosted queued"),
        pytest.param(["ubuntu-latest"], JobStatus.IN_PROGRESS, id="ubuntu latest in progress"),
        pytest.param(
            ["self-hosted", "linux", "amd"], JobStatus.COMPLETED, id="self hosted completed"
        ),
    ],
)
def test_webhook_to_job(labels: list[str], status: JobStatus):
    """
    arrange: A valid payload dict.
    act: Call webhook_to_job with the payload.
    assert: The payload is translated.
    """
    payload = {
        "action": status,
        "workflow_job": {
            "id": 22428484402,
            "run_id": 8200803099,
            "workflow_name": "Push Event Tests",
            "head_branch": "github-hosted",
            "run_url": "https://api.github.com/repos/canonical/f/actions/runs/8200803099",
            "run_attempt": 5,
            "node_id": "CR_kwDOKQMbDc8AAAAFONeDMg",
            "head_sha": "fc670c970f0c5e156a94d1935776d7ed43728067",
            "url": FAKE_JOB_URL,
            "html_url": "https://github.com/f/actions/runs/8200803099/job/22428484402",
            "status": "queued",
            "conclusion": None,
            "created_at": "2024-03-08T08:46:26Z",
            "started_at": "2024-03-08T08:46:26Z",
            "completed_at": None,
            "name": "push-event-tests",
            "steps": [],
            "check_url": "https://api.github.com/repos/f/check-runs/22428484402",
            "labels": labels,
            "runner_id": None,
            "runner_name": None,
            "runner_group_id": None,
            "runner_group_name": None,
        },
    }

    result = webhook_to_job(payload)

    # mypy does not understand that we can pass strings instead of HttpUrl objects
    # because of the underlying pydantic magic
    assert result == Job(labels=labels, status=status, url=FAKE_JOB_URL)  # type: ignore


@pytest.mark.parametrize(
    "labels, status, url",
    [
        pytest.param(
            ["self-hosted", "linux", "arm64"], "invalid", FAKE_JOB_URL, id="invalid status"
        ),
        pytest.param(["ubuntu-latest"], JobStatus.IN_PROGRESS, "invalid", id="invalid run url"),
        pytest.param(None, JobStatus.IN_PROGRESS, FAKE_JOB_URL, id="missing labels"),
        pytest.param(["self-hosted", "linux", "amd"], None, FAKE_JOB_URL, id="missing status"),
        pytest.param(
            ["self-hosted", "linux", "amd"], JobStatus.COMPLETED, None, id="missing run url"
        ),
    ],
)
def test_webhook_invalid_values(labels: list[str], status: JobStatus, url: str):
    """
    arrange: A payload dict with invalid values.
    act: Call webhook_to_job with the payload.
    assert: A ParseError is raised.
    """
    payload = {
        "action": status,
        "workflow_job": {"id": 22428484402, "url": url, "labels": labels},
    }
    with pytest.raises(ParseError) as exc_info:
        webhook_to_job(payload)
    assert "Failed to create Webhook object for webhook " in str(exc_info.value)


def test_webhook_workflow_job_not_dict():
    """
    arrange: A payload dict with workflow_job not a dict.
    act: Call webhook_to_job with the payload.
    assert: A ParseError is raised.
    """
    payload = {
        "action": "queued",
        "workflow_job": "not a dict",
    }
    with pytest.raises(ParseError) as exc_info:
        webhook_to_job(payload)
    assert f"workflow_job is not a dict in {payload}" in str(exc_info.value)


def test_webhook_missing_keys():
    """
    arrange: A payload dict with missing keys.
    act: Call webhook_to_job with the payload.
    assert: A ParseError is raised.
    """
    payload: dict

    # action key is missing
    payload = {
        "payload": {
            "workflow_job": {"id": 22428484402, "url": FAKE_JOB_URL, "labels": FAKE_LABELS},
        },
    }
    with pytest.raises(ParseError) as exc_info:
        webhook_to_job(payload)
    assert f"action key not found in {payload}" in str(exc_info.value)
    # workflow_job key missing
    payload = {
        "action": "queued",
        "id": 22428484402,
        "url": FAKE_JOB_URL,
        "labels": FAKE_LABELS,
    }
    with pytest.raises(ParseError) as exc_info:
        webhook_to_job(payload)
    assert f"workflow_job key not found in {payload}" in str(exc_info.value)

    # labels key missing
    payload = {
        "action": "queued",
        "workflow_job": {"id": 22428484402, "url": FAKE_JOB_URL},
    }
    with pytest.raises(ParseError) as exc_info:
        webhook_to_job(payload)
    assert f"labels key not found in {payload}" in str(exc_info.value)

    # url key missing
    payload = {
        "action": "queued",
        "workflow_job": {"id": 22428484402, "labels": FAKE_LABELS},
    }
    with pytest.raises(ParseError) as exc_info:
        webhook_to_job(payload)
    assert f"url key not found in {payload}" in str(exc_info.value)
