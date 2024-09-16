#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module for parsing the webhook payload."""
from collections import namedtuple
from enum import Enum

from pydantic import BaseModel, HttpUrl

WORKFLOW_JOB = "workflow_job"


ValidationResult = namedtuple("ValidationResult", ["is_valid", "msg"])


class ParseError(Exception):
    """An error occurred during the parsing of the payload."""


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
        url: The URL of the job to be able to check its status.
    """

    labels: list[str]
    status: JobStatus
    url: HttpUrl


def webhook_to_job(webhook: dict) -> Job:
    """Parse a raw json payload and extract the required information.

    Args:
        webhook: The webhook in json to parse.

    Returns:
        The parsed Job.

    Raises:
        ParseError: An error occurred during parsing.
    """
    validation_result = _validate_webhook(webhook)
    if not validation_result.is_valid:
        raise ParseError(f"Could not parse webhook: {validation_result.msg}")

    #  The enclosed code will be removed when compiling to optimised byte code.

    assert "action" in webhook, f"action key not found in {webhook}"  # nosec
    assert "workflow_job" in webhook, f"workflow_job key not found in {webhook}"  # nosec
    assert (  # nosec
        "labels" in webhook["workflow_job"]
    ), f"labels key not found in {webhook['workflow_job']}"
    assert (  # nosec
        "url" in webhook["workflow_job"]
    ), f"url key not found in {webhook['workflow_job']}"

    status = webhook["action"]
    workflow_job = webhook["workflow_job"]

    labels = workflow_job["labels"]
    job_url = workflow_job["url"]

    try:
        return Job(
            labels=labels,
            status=status,
            url=job_url,
        )
    except ValueError as exc:
        raise ParseError(f"Failed to create Webhook object for webhook {webhook}: {exc}") from exc


def _validate_webhook(webhook: dict) -> ValidationResult:
    """Validate the webhook payload.

    Args:
        webhook: The webhook payload to validate.

    Returns:
        (True, "") if the payload is valid otherwise (False, error_msg)
    """
    validation_result = _validate_missing_keys(webhook)
    if not validation_result.is_valid:
        return validation_result

    return ValidationResult(True, "")


def _validate_missing_keys(webhook: dict) -> ValidationResult:
    """Validate the webhook payload for missing keys.

    Uses short-circuit evaluation to check for missing keys.

    Args:
        webhook: The webhook payload to validate.

    Returns:
        (True, "") if all keys are there otherwise (False,error_msg)
         if the payload is missing keys.
    """
    for expected_webhook_key in ("action", "workflow_job"):
        if expected_webhook_key not in webhook:
            return ValidationResult(False, f"{expected_webhook_key} key not found in {webhook}")

    workflow_job = webhook["workflow_job"]
    if not isinstance(workflow_job, dict):
        return ValidationResult(False, f"workflow_job is not a dict in {webhook}")
    for expected_workflow_job_key in ("labels", "url"):
        if expected_workflow_job_key not in workflow_job:
            return ValidationResult(
                False, f"{expected_workflow_job_key} key not found in {webhook}"
            )
    return ValidationResult(True, "")
