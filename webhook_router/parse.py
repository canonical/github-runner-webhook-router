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
        run_url: The URL of the job.
    """

    labels: list[str]
    status: JobStatus
    run_url: HttpUrl


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
    payload = webhook["payload"]
    status = payload["action"]
    workflow_job = payload["workflow_job"]

    labels = workflow_job["labels"]
    run_url = workflow_job["run_url"]

    try:
        return Job(
            labels=labels,
            status=status,
            run_url=run_url,
        )
    except ValueError as exc:
        raise ParseError(f"Failed to create Webhook object for payload {payload}: {exc}") from exc


def _validate_webhook(webhook: dict) -> ValidationResult:
    """Validate the webhook payload.

    Args:
        webhook: The webhook payload to validate.

    Returns:
        (True, "") if the payload is valid otherwise (False, error_msg)
    """
    validation_result = _validate_event(webhook)
    if not validation_result.is_valid:
        return validation_result

    validation_result = _validate_missing_keys(webhook)
    if not validation_result.is_valid:
        return validation_result

    return ValidationResult(True, "")


def _validate_event(webhook: dict) -> ValidationResult:
    """Validate the event key in the webhook payload.

    Args:
        webhook: The webhook payload to validate.

    Returns:
        (True, "") if the event key is valid otherwise (False,error_msg)
    """
    if "event" not in webhook:
        return ValidationResult(False, f"event key not found in {webhook}")
    event = webhook["event"]
    if event != WORKFLOW_JOB:
        return ValidationResult(False, f"Event {event} not supported: {webhook}")
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
    if "payload" not in webhook:
        return ValidationResult(False, f"payload key not found in {webhook}")
    payload = webhook["payload"]
    for payload_key in ["action", "workflow_job"]:
        if payload_key not in payload:
            return ValidationResult(False, f"{payload_key} key not found in {webhook}")

    workflow_job = payload["workflow_job"]
    if not isinstance(workflow_job, dict):
        return ValidationResult(False, f"workflow_job is not a dict in {webhook}")
    for workflow_job_key in ["labels", "run_url"]:
        if workflow_job_key not in workflow_job:
            return ValidationResult(False, f"{workflow_job_key} key not found in {webhook}")
    return ValidationResult(True, "")
