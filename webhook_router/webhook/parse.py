#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module for parsing the webhook payload."""

from webhook_router.webhook import Job

WORKFLOW_JOB = "workflow_job"


class ParseError(Exception):
    """An error occurred during the parsing of the payload."""


def webhook_to_job(webhook: dict) -> Job:
    """Parse a raw json payload and extract the required information.

    Args:
        webhook: The webhook in json to parse.

    Returns:
        The parsed Job.

    Raises:
        ParseError: An error occurred during parsing.
    """
    is_valid, error = _validate_webhook(webhook)
    if not is_valid:
        raise ParseError(f"Could not parse webhook: {error}")
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


def _validate_webhook(webhook: dict) -> tuple[bool, str]:
    """Validate the webhook payload.

    Args:
        webhook: The webhook payload to validate.

    Returns:
        (True, "") if the payload is valid otherwise (False, error_msg)
    """
    is_valid, error = _validate_event(webhook)
    if not is_valid:
        return False, error

    is_valid, error = _validate_missing_keys(webhook)
    if not is_valid:
        return False, error

    return True, ""


def _validate_event(webhook: dict) -> tuple[bool, str]:
    """Validate the event key in the webhook payload.

    Args:
        webhook: The webhook payload to validate.

    Returns:
        (True, "") if the event key is valid otherwise (False,error_msg)
    """
    if "event" not in webhook:
        return False, f"event key not found in {webhook}"
    event = webhook["event"]
    if event != WORKFLOW_JOB:
        return False, f"Event {event} not supported: {webhook}"
    return True, ""


def _validate_missing_keys(webhook: dict) -> tuple[bool, str]:
    """Validate the webhook payload for missing keys.

    Uses short-circuit evaluation to check for missing keys.

    Args:
        webhook: The webhook payload to validate.

    Returns:
        (True, "") if all keys are there otherwise (False,error_msg)
         if the payload is missing keys.
    """
    if "payload" not in webhook:
        return False, f"payload key not found in {webhook}"
    payload = webhook["payload"]
    for payload_key in ["action", "workflow_job"]:
        if payload_key not in payload:
            return False, f"{payload_key} key not found in {webhook}"

    workflow_job = payload["workflow_job"]
    if not isinstance(workflow_job, dict):
        return False, f"workflow_job is not a dict in {webhook}"
    for workflow_job_key in ["labels", "run_url"]:
        if workflow_job_key not in workflow_job:
            return False, f"{workflow_job_key} key not found in {webhook}"
    return True, ""
