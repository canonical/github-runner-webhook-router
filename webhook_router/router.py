#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
"""Module for routing webhooks to the appropriate message queue."""
import itertools
import logging

from pydantic import BaseModel, conlist

from webhook_router.mq import add_job_to_queue
from webhook_router.webhook import Job, JobStatus

logger = logging.getLogger(__name__)

WORKFLOW_JOB = "workflow_job"
LABEL_SEPARATOR = "#"
Flavor = str
Label = str
LabelCombinationIdentifier = str


class RouterError(Exception):
    """Raised when a router error occurs."""


class RoutingTable(BaseModel):
    """A class to represent how to route jobs to the appropriate message queue.

    Attributes:
        mapping: The mapping of labels to flavors.
        ignore_labels: The labels to ignore (e.g. "self-hosted" or "linux").
        default_flavor: The default flavor.
    """

    mapping: dict[LabelCombinationIdentifier, Label]
    ignore_labels: set[Label]
    default_flavor: Flavor


class FlavorLabelsMapping(BaseModel):
    """A class to represent the mapping of flavors to labels.

    Attributes:
        mapping: The mapping of flavors to labels.
    """

    # mypy does not recognize the min_length parameter
    mapping: conlist(item_type=tuple[Flavor, list[Label]], min_length=1)  # type: ignore


def to_routing_table(
    flavor_label_mapping: FlavorLabelsMapping, ignore_labels: set[Label]
) -> RoutingTable:
    """Convert the flavor label mapping to a route table.

    Args:
        flavor_label_mapping: The flavor label mapping.
        ignore_labels: The labels to ignore (e.g. "self-hosted" or "linux").

    Returns:
        The label flavor mapping.
    """
    flavor_mapping = flavor_label_mapping.mapping
    label_mapping = {}
    default_flavor = flavor_mapping[0][0]

    for flavor, labels in flavor_mapping:
        sorted_labels = sorted(labels.lower() for labels in labels)
        powerset = [
            x
            for length in range(1, len(sorted_labels) + 1)
            for x in itertools.combinations(sorted_labels, length)
        ]
        for label_combination in powerset:
            label_key = LABEL_SEPARATOR.join(label_combination)
            if label_key not in label_mapping:
                label_mapping[label_key] = flavor
    return RoutingTable(
        default_flavor=default_flavor,
        mapping=label_mapping,
        ignore_labels={label.lower() for label in ignore_labels},
    )


def forward(job: Job, routing_table: RoutingTable) -> None:
    """Forward the job to the appropriate message queue.

    Args:
        job: The job to forward.
        routing_table: The mapping of labels to flavors.

    Raises:
        RouterError: If the job cannot be forwarded.
    """
    if job.status != JobStatus.QUEUED:
        logger.debug("Received job with status %s. Ignoring.", job.status)
        return

    try:
        flavor = _labels_to_flavor(
            labels=set(job.labels),
            label_flavor_mapping=routing_table,
        )
    except _InvalidLabelCombinationError as e:
        raise RouterError(f"Not able to forward job: {e}") from e

    logger.info("Received job %s for flavor %s", job.json(), flavor)
    add_job_to_queue(job, flavor)


class _InvalidLabelCombinationError(Exception):
    """The label combination is invalid."""


def _labels_to_flavor(labels: set[str], label_flavor_mapping: RoutingTable) -> Flavor:
    """Map the labels to a flavor.

    Args:
        labels: The labels to map.
        label_flavor_mapping: The available flavors.

    Raises:
        _InvalidLabelCombinationError: If the label combination is invalid.

    Returns:
        The flavor.
    """
    if not labels:
        return label_flavor_mapping.default_flavor
    labels_lowered = {label.lower() for label in labels}
    final_labels = labels_lowered - label_flavor_mapping.ignore_labels
    label_key = LABEL_SEPARATOR.join(sorted(final_labels))
    if label_key not in label_flavor_mapping.mapping:
        raise _InvalidLabelCombinationError(f"Invalid label combination: {labels}")
    return label_flavor_mapping.mapping[label_key]
