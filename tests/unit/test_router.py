#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Unit tests for the router module."""
from unittest.mock import MagicMock

import pytest

from webhook_router.mq import add_job_to_queue
from webhook_router.router import RouterError, forward
from webhook_router.webhook import Job, JobStatus
from webhook_router.webhook.label_translation import (
    InvalidLabelCombinationError,
    LabelsFlavorMapping,
    labels_to_flavor,
)


@pytest.fixture(name="labels_to_flavor_mock")
def labels_to_flavor_mock_fixture(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock the labels_to_flavor function."""
    mock = MagicMock(spec=labels_to_flavor)
    monkeypatch.setattr("webhook_router.router.labels_to_flavor", mock)
    return mock


@pytest.fixture(name="add_job_to_queue_mock")
def add_job_to_queue_mock_fixture(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock the add_job_to_queue function."""
    mock = MagicMock(spec=add_job_to_queue)
    monkeypatch.setattr("webhook_router.router.add_job_to_queue", mock)
    return mock


@pytest.mark.usefixtures("labels_to_flavor_mock")
@pytest.mark.parametrize(
    "job_status, is_forwarded",
    [
        pytest.param(JobStatus.COMPLETED, False, id="completed"),
        pytest.param(JobStatus.IN_PROGRESS, False, id="in_progress"),
        pytest.param(JobStatus.WAITING, False, id="waiting"),
        pytest.param(JobStatus.QUEUED, True, id="queued"),
    ],
)
def test_job_is_forwarded(
    job_status: JobStatus,
    is_forwarded: bool,
    add_job_to_queue_mock: MagicMock,
):
    """
    arrange: A job with a status.
    act: Forward the job to the message queue.
    assert: The job is added to the queue if the status is "QUEUED".
    """
    # mypy does not understand that we can pass strings instead of HttpUrl objects
    # because of the underlying pydantic magic
    job = Job(
        labels=["self-hosted", "linux", "arm64"],
        status=job_status,
        run_url="https://api.github.com/repos/f/actions/runs/8200803099",  # type: ignore
    )
    forward(
        job,
        route_table=LabelsFlavorMapping(mapping={}, default_flavor="default", ignore_labels=set()),
    )

    assert add_job_to_queue_mock.called == is_forwarded


def test_invalid_label_combination(labels_to_flavor_mock: MagicMock):
    """
    arrange: A job with an invalid label combination.
    act: Forward the job to the message queue.
    assert: A RouterError is raised.
    """
    labels_to_flavor_mock.side_effect = InvalidLabelCombinationError("Invalid label combination")
    # mypy does not understand that we can pass strings instead of HttpUrl objects
    # because of the underlying pydantic magic
    job = Job(
        labels=["self-hosted", "linux", "arm64", "x64"],
        status=JobStatus.QUEUED,
        run_url="https://api.github.com/repos/f/actions/runs/8200803099",  # type: ignore
    )
    with pytest.raises(RouterError) as e:
        forward(
            job,
            route_table=LabelsFlavorMapping(
                mapping={}, default_flavor="default", ignore_labels=set()
            ),
        )
    assert str(e.value) == "Not able to forward job: Invalid label combination"
