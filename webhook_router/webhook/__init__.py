#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.
"""Package for webhook related functionality."""

from enum import Enum

from pydantic import BaseModel, HttpUrl


class JobStatus(str, Enum):
    """The status of the job.

    Attributes:
        COMPLETED: The job is completed.
        IN_PROGRESS: The job is in progress.
        QUEUED: The job is queued.
        WAITING: The job is waiting.
    """

    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    QUEUED = "queued"
    WAITING = "waiting"


class Job(BaseModel):
    """A class to translate the payload.

    Attributes:
        labels: The labels of the job.
        status: The status of the job.
        run_url: The URL of the job.
    """

    labels: list[str]
    status: JobStatus
    run_url: HttpUrl
