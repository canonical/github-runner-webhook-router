#  Copyright 2026 Canonical Ltd.
#  See LICENSE file for licensing details.
"""Module for routing webhooks to the appropriate message queue."""
import itertools
import json
import logging

from pydantic import BaseModel

from webhook_router import mq
from webhook_router.parse import Job, JobStatus

logger = logging.getLogger(__name__)

ROUTABLE_JOB_STATUS = JobStatus.QUEUED
Flavor = str
Label = str
LabelCombinationIdentifier = tuple[Label, ...]


class NonForwardableJobError(Exception):
    """Raised when a job cannot be forwarded due to non-matching labels in the routing table."""


class RoutingTable(BaseModel):
    """A class to represent how to route jobs to the appropriate message queue.

    Attributes:
        value: The mapping of labels to flavors.
        default_flavor: The default flavor.
    """

    value: dict[LabelCombinationIdentifier, Label]
    default_flavor: Flavor


FlavorLabelsMappingList = list[tuple[Flavor, list[Label]]]


def to_routing_table(
    flavor_label_mapping_list: FlavorLabelsMappingList, default_flavor: Flavor
) -> RoutingTable:
    """Convert the flavor label mapping to a route table.

    Args:
        flavor_label_mapping_list: The list of mappings of flavors to labels.
        default_flavor: The default flavor to use if no labels are provided.

    Returns:
        The label flavor mapping.
    """
    routing_table: dict[tuple[Label, ...], Flavor] = {}

    for flavor, labels in flavor_label_mapping_list:
        # Use the sorted labels as keys for the routing table.

        sorted_labels = tuple(sorted(labels.lower() for labels in labels))

        # We have to consider every combination of labels provided for a flavor.
        # E.g. if we have a flavor label mapping
        #
        # - "large": ["large", "x64", "jammy"]
        # - "edge": ["edge", "x64"],
        #
        #  we have to route the label combinations
        #
        # ["large"], ["x64"], ["jammy"], ["large", "x64"] to "large" and
        # ["edge"], ["edge", "x64"] to "edge"
        #
        # as we cannot rely on the user to provide all the labels in a workflow job.
        label_combinations = [
            x
            for length in range(1, len(sorted_labels) + 1)
            for x in itertools.combinations(sorted_labels, length)
        ]
        route_entries_for_flavor = {
            label_combination: flavor for label_combination in label_combinations
        }

        # Merge these route entries with existing ones, preserving the existing mappings to
        # avoid overwriting them and respecting the order of the entries given by the operator.
        routing_table = {
            **route_entries_for_flavor,
            **routing_table,
        }
    return RoutingTable(
        default_flavor=default_flavor,
        value=routing_table,
    )


def forward(job: Job, routing_table: RoutingTable) -> None:
    """Forward the job to the appropriate message queue.

    Args:
        job: The job to forward.
        routing_table: The mapping of labels to flavors.

    Raises:
        NonForwardableJobError: If the job cannot be forwarded.
    """
    if job.status != ROUTABLE_JOB_STATUS:
        logger.debug("Received job with status %s. Ignoring.", job.status)
        return

    try:
        flavor = _labels_to_flavor(
            labels=set(job.labels),
            routing_table=routing_table,
        )
    except _InvalidLabelCombinationError as e:
        raise NonForwardableJobError(f"Not able to forward job: {e}") from e

    logger.info(
        json.dumps(
            {
                "log_type": "job_forwarded",
                "labels": list(job.labels),
                "url": str(job.url),
                "flavor": flavor,
            }
        )
    )
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
    labels_lowered = {label.lower() for label in labels}
    if not labels_lowered:
        return routing_table.default_flavor

    label_key = tuple(sorted(labels_lowered))
    if label_key not in routing_table.value:
        raise _InvalidLabelCombinationError(f"Invalid label combination: {labels}")
    return routing_table.value[label_key]
