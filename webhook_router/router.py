#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
"""Module for routing webhooks to the appropriate message queue."""
import itertools
import logging

from pydantic import BaseModel

from webhook_router import mq
from webhook_router.parse import Job, JobStatus

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
        value: The mapping of labels to flavors.
        ignore_labels: The labels to ignore (e.g. "self-hosted" or "linux").
        default_flavor: The default flavor.
    """

    value: dict[LabelCombinationIdentifier, Label]
    ignore_labels: set[Label]
    default_flavor: Flavor


FlavorLabelsMappingList = list[tuple[Flavor, list[Label]]]


def to_routing_table(
    flavor_label_mapping_list: FlavorLabelsMappingList,
    ignore_labels: set[Label],
    default_flavor: Flavor,
) -> RoutingTable:
    """Convert the flavor label mapping to a route table.

    Args:
        flavor_label_mapping_list: The list of mappings of flavors to labels.
        ignore_labels: The labels to ignore (e.g. "self-hosted" or "linux").
        default_flavor: The default flavor to use if no labels are provided.

    Returns:
        The label flavor mapping.
    """
    label_mapping = {}

    for flavor, labels in flavor_label_mapping_list:
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
        value=label_mapping,
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
            routing_table=routing_table,
        )
    except _InvalidLabelCombinationError as e:
        raise RouterError(f"Not able to forward job: {e}") from e

    logger.info("Received job %s for flavor %s", job.json(), flavor)
    mq.add_job_to_queue(job, flavor)


def can_forward() -> bool:
    """Check if the router can forward jobs.

    Returns:
        True if the router can forward jobs otherwise False.
    """
    return mq.can_connect()


class _InvalidLabelCombinationError(Exception):
    """The label combination is invalid."""


def _labels_to_flavor(labels: set[str], routing_table: RoutingTable) -> Flavor:
    """Map the labels to a flavor.

    Args:
        labels: The labels to map.
        routing_table: The available flavors.

    Raises:
        _InvalidLabelCombinationError: If the label combination is invalid.

    Returns:
        The flavor.
    """
    if not labels:
        return routing_table.default_flavor
    labels_lowered = {label.lower() for label in labels}
    final_labels = labels_lowered - routing_table.ignore_labels
    label_key = LABEL_SEPARATOR.join(sorted(final_labels))
    if label_key not in routing_table.value:
        raise _InvalidLabelCombinationError(f"Invalid label combination: {labels}")
    return routing_table.value[label_key]
