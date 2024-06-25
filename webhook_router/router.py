#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
"""Module for routing webhooks to the appropriate message queue."""

import logging

from webhook_router.mq import add_job_to_queue
from webhook_router.webhook import Job, JobStatus
from webhook_router.webhook.label_translation import (
    InvalidLabelCombinationError,
    LabelsFlavorMapping,
    labels_to_flavor,
)

logger = logging.getLogger(__name__)


class RouterError(Exception):
    """Raised when a router error occurs."""


def forward(job: Job, route_table: LabelsFlavorMapping) -> None:
    """Forward the job to the appropriate message queue.

    Args:
        job: The job to forward.
        route_table: The mapping of labels to flavors.

    Raises:
        RouterError: If the job cannot be forwarded.
    """
    if job.status != JobStatus.QUEUED:
        logger.debug("Received job with status %s. Ignoring.", job.status)
        return

    try:
        flavor = labels_to_flavor(
            labels=set(job.labels),
            label_flavor_mapping=route_table,
        )
    except InvalidLabelCombinationError as e:
        raise RouterError(f"Not able to forward job: {e}") from e

    logger.info("Received job %s for flavor %s", job.json(), flavor)
    add_job_to_queue(job, flavor)
