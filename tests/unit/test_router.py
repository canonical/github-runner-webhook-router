#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Unit tests for the router module."""
import itertools
from unittest.mock import MagicMock

import pytest

from webhook_router.mq import add_job_to_queue
from webhook_router.parse import Job, JobStatus
from webhook_router.router import (
    LABEL_SEPARATOR,
    FlavorLabelsMapping,
    RouterError,
    RoutingTable,
    _InvalidLabelCombinationError,
    _labels_to_flavor,
    forward,
    to_routing_table,
)


@pytest.fixture(name="add_job_to_queue_mock")
def add_job_to_queue_mock_fixture(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock the add_job_to_queue function."""
    mock = MagicMock(spec=add_job_to_queue)
    monkeypatch.setattr("webhook_router.router.add_job_to_queue", mock)
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
        labels=["arm64"],
        status=job_status,
        run_url="https://api.github.com/repos/f/actions/runs/8200803099",  # type: ignore
    )
    forward(
        job,
        routing_table=RoutingTable(
            mapping={"arm64": "arm64"}, default_flavor="arm64", ignore_labels=set()
        ),
    )

    assert add_job_to_queue_mock.called == is_forwarded


def test_invalid_label_combination():
    """
    arrange: A job with an invalid label combination.
    act: Forward the job to the message queue.
    assert: A RouterError is raised.
    """
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
            routing_table=RoutingTable(mapping={}, default_flavor="default", ignore_labels=set()),
        )
    assert "Not able to forward job: Invalid label combination:" in str(e.value)


def test_to_routing_table():
    """
    arrange: A mapping of flavors to labels.
    act: Call to_routing_table with the mapping.
    assert: A LabelsFlavorMapping object is returned.
    """
    flavor_mapping = FlavorLabelsMapping(
        mapping=[("large", ["arm64", "large"]), ("x64-large", ["large", "x64", "jammy"])]
    )
    ignore_labels = {"self-hosted", "linux"}
    default_flavor = "x64-large"
    routing_table = to_routing_table(flavor_mapping, ignore_labels, default_flavor)
    assert routing_table == RoutingTable(
        mapping={
            "arm64": "large",
            "large": "large",
            f"arm64{LABEL_SEPARATOR}large": "large",
            "x64": "x64-large",
            "jammy": "x64-large",
            f"jammy{LABEL_SEPARATOR}x64": "x64-large",
            f"jammy{LABEL_SEPARATOR}large": "x64-large",
            f"large{LABEL_SEPARATOR}x64": "x64-large",
            f"jammy{LABEL_SEPARATOR}large{LABEL_SEPARATOR}x64": "x64-large",
        },
        default_flavor="x64-large",
        ignore_labels=ignore_labels,
    )


def test_to_routing_table_case_insensitive():
    """
    arrange: A mapping of flavors to labels with labels in mixed case.
    act: Call to_routing_table with the mapping.
    assert: A LabelsFlavorMapping object is returned which has all labels in lower case.
    """
    flavor_mapping = FlavorLabelsMapping(mapping=[("large", ["arM64", "LaRgE"])])
    ignore_labels = {"self-HOSTED", "LINux"}
    default_flavor = "large"
    routing_table = to_routing_table(flavor_mapping, ignore_labels, default_flavor)
    assert routing_table == RoutingTable(
        mapping={
            "arm64": "large",
            "large": "large",
            f"arm64{LABEL_SEPARATOR}large": "large",
        },
        default_flavor="large",
        ignore_labels={"self-hosted", "linux"},
    )


def test_labels_to_flavor():
    """
    arrange: Two flavors and a labels to flavor mapping
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
    mapping = RoutingTable(
        mapping={
            **{
                LABEL_SEPARATOR.join(label_combination): "large"
                for label_combination in arm_label_combination
            },
            **{
                LABEL_SEPARATOR.join(label_combination): "x64-large"
                for label_combination in x64_label_combination
            },
        },
        default_flavor="large",
        ignore_labels={"self-hosted", "linux"},
    )

    for label_combination in arm_label_combination:
        assert (
            _labels_to_flavor(set(label_combination), mapping) == "large"
        ), f"Expected large flavor for {label_combination}"

    for label_combination in x64_label_combination:
        assert (
            _labels_to_flavor(set(label_combination), mapping) == "x64-large"
        ), f"Expected x64-large flavor for {label_combination}"


def test_labels_to_flavor_case_insensitive():
    """
    arrange: Two flavors and a labels to flavor mapping
    act: Call labels_to_flavor with all combination of labels in mixed case.
    assert: The correct flavor is returned.
    """
    mapping = RoutingTable(
        mapping={
            "small": "small",
            "arm64": "large",
            "large": "large",
            f"arm64{LABEL_SEPARATOR}large": "large",
        },
        default_flavor="large",
        ignore_labels={"self-hosted", "linux"},
    )

    assert _labels_to_flavor({"SMALl"}, mapping) == "small"
    assert _labels_to_flavor({"ARM64"}, mapping) == "large"
    assert _labels_to_flavor({"lARGE"}, mapping) == "large"
    assert _labels_to_flavor({"arM64", "lArge"}, mapping) == "large"
    assert _labels_to_flavor({"small", "SELF-hosted"}, mapping) == "small"


def test_labels_to_flavor_default_label():
    """
    arrange: Two flavors and a labels to flavor mapping
    act: Call labels_to_flavor with empty labels.
    assert: The default flavor is returned.
    """
    mapping = RoutingTable(
        mapping={
            "arm64": "large",
            "large": "large",
            f"arm64{LABEL_SEPARATOR}large": "large",
            "x64": "large-x64",
            f"large{LABEL_SEPARATOR}x64": "x64-large",
        },
        default_flavor="large",
        ignore_labels={"self-hosted", "linux"},
    )
    assert _labels_to_flavor(set(), mapping) == "large"


def test_labels_to_flavor_invalid_combination():
    """
    arrange: Two flavors and a labels to flavor mapping
    act: Call labels_to_flavor with an invalid combination.
    assert: An InvalidLabelCombinationError is raised.
    """
    mapping = RoutingTable(
        mapping={
            "arm64": "large",
            "large": "large",
            f"arm64{LABEL_SEPARATOR}large": "large",
            "x64": "large-x64",
            f"large{LABEL_SEPARATOR}x64": "x64-large",
        },
        default_flavor="large",
        ignore_labels={"self-hosted", "linux"},
    )
    labels = {"self-hosted", "linux", "arm64", "large", "x64"}
    with pytest.raises(_InvalidLabelCombinationError) as exc_info:
        _labels_to_flavor(labels, mapping)
    assert "Invalid label combination:" in str(exc_info.value)


def test_labels_to_flavor_unrecognised_label():
    """
    arrange: Two flavors and a labels to flavor mapping
    act: Call labels_to_flavor with an unrecognised label.
    assert: An InvalidLabelCombinationError is raised.
    """
    mapping = RoutingTable(
        mapping={
            "arm64": "large",
            "large": "large",
            f"arm64{LABEL_SEPARATOR}large": "large",
            "x64": "large-x64",
            f"large{LABEL_SEPARATOR}x64": "x64-large",
        },
        default_flavor="large",
        ignore_labels={"self-hosted", "linux"},
    )
    labels = {"self-hosted", "linux", "arm64", "large", "noble"}
    with pytest.raises(_InvalidLabelCombinationError) as exc_info:
        _labels_to_flavor(labels, mapping)
    assert "Invalid label combination:" in str(exc_info.value)


def test_labels_to_flavor_ignore_labels():
    """
    arrange: Two flavors and a labels to flavor mapping
    act: Call labels_to_flavor with an ignored label.
    assert: The correct flavor is returned.
    """
    mapping = RoutingTable(
        mapping={
            "arm64": "large",
            "large": "large",
            f"arm64{LABEL_SEPARATOR}large": "large",
            "x64": "large-x64",
            f"large{LABEL_SEPARATOR}x64": "x64-large",
        },
        default_flavor="large",
        ignore_labels={"self-hosted", "linux"},
    )
    labels = {"self-hosted", "linux", "arm64", "large"}
    assert _labels_to_flavor(labels, mapping) == "large"
