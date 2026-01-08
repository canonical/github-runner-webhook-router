#  Copyright 2026 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module for parsing the webhook payload."""
from collections import namedtuple
from enum import Enum
from typing import Collection

from pydantic import BaseModel, HttpUrl

ValidationResult = namedtuple("ValidationResult", ["is_valid", "msg"])
Labels = set[str]


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

    labels: Labels
    status: JobStatus
    url: HttpUrl


def webhook_to_job(payload: dict, ignore_labels: Collection[str]) -> Job:
    """Parse a raw json payload and extract the required information.

    Args:
        payload: The webhook's payload in json to parse.
        ignore_labels: The labels to ignore when parsing. For example, "self-hosted" or "linux".

    Returns:
        The parsed Job.

    Raises:
        ParseError: An error occurred during parsing.
    """
    validation_result = _validate_webhook(payload)
    if not validation_result.is_valid:
        raise ParseError(f"Could not parse webhook: {validation_result.msg}")

    #  The enclosed code will be removed when compiling to optimised byte code.

    assert "action" in payload, f"action key not found in {payload}"  # nosec
    assert "workflow_job" in payload, f"workflow_job key not found in {payload}"  # nosec
    assert (  # nosec
        "labels" in payload["workflow_job"]
    ), f"labels key not found in {payload['workflow_job']}"
    assert (  # nosec
        "url" in payload["workflow_job"]
    ), f"url key not found in {payload['workflow_job']}"

    status = payload["action"]
    workflow_job = payload["workflow_job"]

    labels = workflow_job["labels"]

    if labels is None:
        raise ParseError(
            f"Failed to create Webhook object for webhook {payload}: Labels are missing"
        )

    job_url = workflow_job["url"]

    try:
        return Job(
            labels=_parse_labels(labels=labels, ignore_labels=ignore_labels),
            status=status,
            url=job_url,
        )
    except ValueError as exc:
        raise ParseError(f"Failed to create Webhook object for webhook {payload}: {exc}") from exc


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


def _parse_labels(labels: Collection[str], ignore_labels: Collection[str]) -> Labels:
    """Parse the labels coming from the payload and remove the ignore labels.

    Args:
        labels: The labels to parse from the payload.
        ignore_labels: The labels to ignore.

    Returns:
        The parsed labels in lowercase.
    """
    return {label.lower() for label in labels} - {
        ignore_label.lower() for ignore_label in ignore_labels
    }
