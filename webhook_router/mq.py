#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module for interacting with the message queue."""
import logging
import os

from kombu import Connection

from webhook_router.webhook import Job

MONGODB_DB_CONNECT_STR = os.getenv("MONGODB_DB_CONNECT_STRING")


logger = logging.getLogger(__name__)

logger.info("Using MongoDB at %s", MONGODB_DB_CONNECT_STR)


def add_job_to_queue(job: Job, flavor: str) -> None:
    """Forward the webhook to the message queue.

    Args:
        job: The job to add to the queue.
        flavor: The flavor to add the job to.
    """
    _add_to_queue(job.json(), flavor)


def _add_to_queue(msg: str, queue_name: str) -> None:
    """Add a message to a queue.

    Args:
        msg: The message to add to the queue.
        queue_name: The name of the queue to add the message to.
    """
    with Connection(MONGODB_DB_CONNECT_STR) as conn:
        simple_queue = conn.SimpleQueue(queue_name)

        simple_queue.put(msg, retry=True)
        logger.debug("Sent: %s to queue %s", msg, queue_name)
        simple_queue.close()
