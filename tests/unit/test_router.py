#  Copyright 2026 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Unit tests for the router module."""
import itertools
from unittest.mock import MagicMock

import pytest

from webhook_router.mq import add_job_to_queue
from webhook_router.parse import Job, JobStatus
from webhook_router.router import (
    NonForwardableJobError,
    RoutingTable,
    _InvalidLabelCombinationError,
    _labels_to_flavor,
    can_forward,
    forward,
    to_routing_table,
)


@pytest.fixture(name="add_job_to_queue_mock")
def add_job_to_queue_mock_fixture(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock the add_job_to_queue function."""
    mock = MagicMock(spec=add_job_to_queue)
    monkeypatch.setattr("webhook_router.router.mq.add_job_to_queue", mock)
    return mock


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
        labels={"arm64"},
        status=job_status,
        url="https://api.github.com/repos/f/actions/jobs/8200803099",  # type: ignore
    )
    forward(
        job,
        routing_table=RoutingTable(value={("arm64",): "arm64"}, default_flavor="arm64"),
    )

    assert add_job_to_queue_mock.called == is_forwarded


def test_invalid_label_combination():
    """
    arrange: A job with an invalid label combination.
    act: Forward the job to the message queue.
    assert: A NonForwardableJobError is raised.
    """
    # mypy does not understand that we can pass strings instead of HttpUrl objects
    # because of the underlying pydantic magic
    job = Job(
        labels={"self-hosted", "linux", "arm64", "x64"},
        status=JobStatus.QUEUED,
        url="https://api.github.com/repos/f/actions/jobs/8200803099",  # type: ignore
    )
    with pytest.raises(NonForwardableJobError) as e:
        forward(
            job,
            routing_table=RoutingTable(value={}, default_flavor="default"),
        )
    assert "Not able to forward job: Invalid label combination:" in str(e.value)


def test_to_routing_table():
    """
    arrange: A mapping of flavors to labels.
    act: Call to_routing_table with the mapping.
    assert: A LabelsFlavorMapping object is returned.
    """
    flavor_mapping = [("large", ["arm64", "large"]), ("x64-large", ["large", "x64", "jammy"])]

    default_flavor = "x64-large"
    routing_table = to_routing_table(flavor_mapping, default_flavor)
    assert routing_table == RoutingTable(
        value={
            ("arm64",): "large",
            ("large",): "large",
            ("arm64", "large"): "large",
            ("x64",): "x64-large",
            ("jammy",): "x64-large",
            ("jammy", "x64"): "x64-large",
            ("jammy", "large"): "x64-large",
            ("large", "x64"): "x64-large",
            ("jammy", "large", "x64"): "x64-large",
        },
        default_flavor="x64-large",
    )


def test_to_routing_table_case_insensitive():
    """
    arrange: A mapping of flavors to labels with labels in mixed case.
    act: Call to_routing_table with the mapping.
    assert: A LabelsFlavorMapping object is returned which has all labels in lower case.
    """
    flavor_mapping = [("large", ["arM64", "LaRgE"])]
    default_flavor = "large"
    routing_table = to_routing_table(flavor_mapping, default_flavor)
    assert routing_table == RoutingTable(
        value={
            ("arm64",): "large",
            ("large",): "large",
            ("arm64", "large"): "large",
        },
        default_flavor="large",
    )


def test_can_forward(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: A mock for mq.can_connect setup with True and False.
    act: Call can_forward.
    assert: True is returned if the connection is successful otherwise False.
    """
    monkeypatch.setattr("webhook_router.router.mq.can_connect", MagicMock(return_value=True))
    assert can_forward() is True

    monkeypatch.setattr("webhook_router.router.mq.can_connect", MagicMock(return_value=False))
    assert can_forward() is False


def test__labels_to_flavor():
    """
    arrange: Two flavors and a routing_table
    act: Call labels_to_flavor with all combination of labels.
    assert: The correct flavor is returned.
    """
    arm_flavor_labels = ["arm64", "jammy", "large"]
    x64_flavor_labels = ["large", "noble", "x64"]
    arm_label_combination = set(
        x
        for length in range(1, len(arm_flavor_labels) + 1)
        for x in itertools.combinations(arm_flavor_labels, length)
    )
    x64_label_combination = set(
        x
        for length in range(1, len(x64_flavor_labels) + 1)
        for x in itertools.combinations(x64_flavor_labels, length)
    )
    x64_label_combination.remove(("large",))
    routing_table = RoutingTable(
        value={
            **{label_combination: "large" for label_combination in arm_label_combination},
            **{label_combination: "x64-large" for label_combination in x64_label_combination},
        },
        default_flavor="large",
    )

    for label_combination in arm_label_combination:
        assert (
            _labels_to_flavor(set(label_combination), routing_table) == "large"
        ), f"Expected large flavor for {label_combination}"

    for label_combination in x64_label_combination:
        assert (
            _labels_to_flavor(set(label_combination), routing_table) == "x64-large"
        ), f"Expected x64-large flavor for {label_combination}"


def test__labels_to_flavor_case_insensitive():
    """
    arrange: Two flavors and a routing_table
    act: Call labels_to_flavor with all combination of labels in mixed case.
    assert: The correct flavor is returned.
    """
    routing_table = RoutingTable(
        value={
            ("small",): "small",
            ("arm64",): "large",
            ("large",): "large",
            ("arm64", "large"): "large",
        },
        default_flavor="large",
    )

    assert _labels_to_flavor({"SMALl"}, routing_table) == "small"
    assert _labels_to_flavor({"ARM64"}, routing_table) == "large"
    assert _labels_to_flavor({"lARGE"}, routing_table) == "large"
    assert _labels_to_flavor({"arM64", "lArge"}, routing_table) == "large"
    assert _labels_to_flavor({"small"}, routing_table) == "small"


def test__labels_to_flavor_default_flavor():
    """
    arrange: Two flavors and a labels to flavor routing_table
    act: Call labels_to_flavor with empty labels.
    assert: The default flavor is returned.
    """
    routing_table = RoutingTable(
        value={
            ("arm64",): "large",
            ("large",): "large",
            ("arm64", "large"): "large",
            ("x64",): "large-x64",
            ("large", "x64"): "x64-large",
        },
        default_flavor="large",
    )
    assert _labels_to_flavor(set(), routing_table) == "large"


def test__labels_to_flavor_invalid_combination():
    """
    arrange: Two flavors and a labels to flavor routing_table
    act: Call labels_to_flavor with an invalid combination.
    assert: An InvalidLabelCombinationError is raised.
    """
    routing_table = RoutingTable(
        value={
            ("arm64",): "large",
            ("large",): "large",
            ("arm64", "large"): "large",
            ("x64",): "large-x64",
            ("large", "x64"): "x64-large",
        },
        default_flavor="large",
    )
    labels = {"self-hosted", "linux", "arm64", "large", "x64"}
    with pytest.raises(_InvalidLabelCombinationError) as exc_info:
        _labels_to_flavor(labels, routing_table)
    assert "Invalid label combination:" in str(exc_info.value)


def test__labels_to_flavor_unrecognised_label():
    """
    arrange: Two flavors and a labels to flavor routing_table
    act: Call labels_to_flavor with an unrecognised label.
    assert: An InvalidLabelCombinationError is raised.
    """
    routing_table = RoutingTable(
        value={
            ("arm64",): "large",
            ("large",): "large",
            ("arm64", "large"): "large",
            ("x64",): "large-x64",
            ("large", "x64"): "x64-large",
        },
        default_flavor="large",
    )
    labels = {"self-hosted", "linux", "arm64", "large", "noble"}
    with pytest.raises(_InvalidLabelCombinationError) as exc_info:
        _labels_to_flavor(labels, routing_table)
    assert "Invalid label combination:" in str(exc_info.value)
