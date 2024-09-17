#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module for parsing the webhook payload."""
from collections import namedtuple
from enum import Enum

from pydantic import BaseModel

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


class GitHubRepo(BaseModel):
    """A class to represent the GitHub repository.

    Attributes:
        owner: The owner of the repository.
        name: The name of the repository.
    """

    owner: str
    name: str


class Job(BaseModel):
    """A class to translate the payload.

    Attributes:
        labels: The labels of the job.
        status: The status of the job.
        repository: The repository of the job.
        id: The id of the job.
    """

    labels: list[str]
    status: JobStatus
    repository: GitHubRepo
    id: int


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
    assert (
        "id" in webhook["workflow_job"]
    ), f"id key not found in {webhook['workflow_job']}"  # nosec
    assert "repository" in webhook, f"repository key not found in {webhook}"  # nosec
    assert (
        "name" in webhook["repository"]
    ), f"name key not found in {webhook['repository']}"  # nosec
    assert (
        "owner" in webhook["repository"]
    ), f"owner key not found in {webhook['repository']}"  # nosec
    assert (
        "login" in webhook["repository"]["owner"]
    ), f"login key not found in {webhook['repository']['owner']}"  # nosec

    status = webhook["action"]
    workflow_job = webhook["workflow_job"]

    labels = workflow_job["labels"]
    repository = GitHubRepo(
        owner=webhook["repository"]["owner"]["login"], name=webhook["repository"]["name"]
    )
    job_id = workflow_job["id"]

    try:
        return Job(
            labels=labels,
            status=status,
            repository=repository,
            id=job_id,
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
    key_hierachy = {
        "action": {},
        "workflow_job": {
            "labels": {},
            "id": {},
        },
        "repository": {
            "name": {},
            "owner": {
                "login": {},
            },
        },
    }
    return _validate_missing_keys(webhook, key_hierachy)


def _validate_missing_keys(root: dict, key_hierarchy: dict) -> ValidationResult:
    """Validate the payload for missing keys.

    This is a recursive function that will validate the payload for missing keys.

    Args:
        root: The root inside the webhook from which to start the validation.
        key_hierarchy: The key hierarchy to validate.

    Returns:
        (True, "") if all keys are there otherwise (False,error_msg)
         if the payload is missing keys.
    """
    for key, sub_keys in key_hierarchy.items():
        if key not in root:
            return ValidationResult(False, f"{key} key not found in {root}")

        if sub_keys:
            if not isinstance(root[key], dict):
                return ValidationResult(False, f"{key} is not a dict in {root}")
            validation_result = _validate_missing_keys(root[key], sub_keys)
            if not validation_result.is_valid:
                return validation_result

    return ValidationResult(True, "")
