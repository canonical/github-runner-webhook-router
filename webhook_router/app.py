#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Flask application which receives GitHub webhooks and logs those."""
import logging
from collections import namedtuple

import yaml
from flask import Flask, request

from webhook_router.mq import add_job_to_queue
from webhook_router.validation import verify_signature
from webhook_router.webhook import Job, JobStatus
from webhook_router.webhook.label_translation import (
    FlavorLabelsMapping,
    InvalidLabelCombinationError,
    labels_to_flavor,
    to_labels_flavor_mapping,
)
from webhook_router.webhook.parse import ParseError, webhook_to_job

SUPPORTED_GITHUB_EVENT = "workflow_job"
GITHUB_EVENT_HEADER = "X-Github-Event"
WEBHOOK_SIGNATURE_HEADER = "X-Hub-Signature-256"

ValidationResult = namedtuple("ValidationResult", ["is_valid", "msg"])

app = Flask(__name__.split(".", maxsplit=1)[0])


class ConfigError(Exception):
    """Raised when a configuration error occurs."""


def config_app(flask_app: Flask) -> None:
    """Configure the application.

    Args:
        flask_app: The Flask application to configure.
    """
    flask_app.config.from_prefixed_env()
    flavor_labels_mapping = _parse_flavor_labels_mapping(flask_app.config.get("FLAVOURS", ""))
    default_self_hosted_labels = _parse_default_self_hosted_labels_config(
        flask_app.config.get("DEFAULT_SELF_HOSTED_LABELS", "")
    )
    flask_app.config["LABEL_FLAVOR_MAPPING"] = to_labels_flavor_mapping(
        flavor_labels_mapping,
        ignore_labels=default_self_hosted_labels,
    )


def _parse_flavor_labels_mapping(flavors_config: str) -> FlavorLabelsMapping:
    """Get the flavor labels mapping.

    Args:
        flavors_config: The flavors to get the mapping for.

    Returns:
        The flavor labels mapping.

    Raises:
        ConfigError: If the FLAVOURS config is invalid.
    """
    if not flavors_config:
        raise ConfigError("FLAVOURS config is not set!")

    try:
        flavor_labels_mapping = yaml.safe_load(flavors_config)
    except yaml.YAMLError as exc:
        raise ConfigError("Invalid 'FLAVOURS' config. Invalid yaml.") from exc
    if not isinstance(flavor_labels_mapping, list):
        raise ConfigError(
            "Invalid 'FLAVOURS' config. Expected a YAML file with a list at the top level."
        )
    flavor_labels_mapping = [tuple(item.items())[0] for item in flavor_labels_mapping]
    try:
        return FlavorLabelsMapping(mapping=flavor_labels_mapping)
    except ValueError as exc:
        raise ConfigError("Invalid 'FLAVOURS' config. Invalid format.") from exc


def _parse_default_self_hosted_labels_config(github_default_labels_config: str) -> set[str]:
    """Get the default labels from the config.

    Args:
        github_default_labels_config: The default labels config.

    Returns:
        The default labels.

    Raises:
        ConfigError: If the DEFAULT_SELF_HOSTED_LABELS config is invalid.
    """
    if not (labels := github_default_labels_config):
        raise ConfigError("DEFAULT_SELF_HOSTED_LABELS config is not set!")
    return set(labels.split(","))


@app.route("/health", methods=["GET"])
def health_check() -> tuple[str, int]:
    """Health check endpoint.

    Returns:
        A tuple containing an empty string and 200 status code.
    """
    return "", 200


@app.route("/webhook", methods=["POST"])
def handle_github_webhook() -> tuple[str, int]:
    """Receive a GitHub webhook and append the payload to a file.

    Returns:
        A tuple containing an empty string and 200 status code on success or
        a failure message and 4xx status code.
    """
    if secret := app.config.get("WEBHOOK_SECRET"):
        validation_result = _validate_signature(secret)
        if not validation_result.is_valid:
            return validation_result.msg, 403

    validation_result = _validate_github_event_header()
    if not validation_result.is_valid:
        return validation_result.msg, 400

    try:
        job = _parse_job()
    except ParseError as exc:
        app.logger.error("Failed to parse webhook payload: %s", exc)
        return str(exc), 400

    app.logger.debug("Parsed job: %s", job)

    if job.status == JobStatus.QUEUED:
        try:
            _forward_to_mq(job)
        except InvalidLabelCombinationError as exc:
            app.logger.error(str(exc))
            return str(exc), 400
    else:
        logging.debug("Received job with status %s. Ignoring.", job.status)
    return "", 200


def _validate_signature(secret: str) -> ValidationResult:
    """Validate the webhook signature.

    Args:
        secret: The secret to validate the signature.

    Returns:
        A tuple containing a boolean indicating if the signature is valid and a message
        on failure.
    """
    if not (signature := request.headers.get(WEBHOOK_SIGNATURE_HEADER)):
        app.logger.debug(
            "X-Hub-signature-256 header is missing in request from %s", request.origin
        )
        return ValidationResult(is_valid=False, msg="X-Hub-signature-256 header is missing!")

    if not verify_signature(payload=request.data, secret_token=secret, signature_header=signature):
        app.logger.debug("Signature validation failed in request from %s", request.origin)
        return ValidationResult(is_valid=False, msg="Signature validation failed!")

    return ValidationResult(is_valid=True, msg="")


def _validate_github_event_header() -> ValidationResult:
    """Validate the GitHub event header.

    Returns:
        A tuple containing a boolean indicating if the event is valid and a message
        on failure.
    """
    if (event := request.headers.get(GITHUB_EVENT_HEADER)) != SUPPORTED_GITHUB_EVENT:
        if event:
            msg = f"Webhook event {event} not supported!"
            app.logger.debug(
                "Received not supported webhook event from %s: %s", event, request.origin
            )
        else:
            msg = "X-Github-Event header is missing!"
            app.logger.debug("X-Github-Event header is missing in request from %s", request.origin)
        return ValidationResult(is_valid=False, msg=msg)

    return ValidationResult(is_valid=True, msg="")


def _parse_job() -> Job:
    """Parse the job from the request.

    Returns:
        The parsed job.
    """
    payload = request.get_json()
    app.logger.debug("Received payload: %s", payload)
    return webhook_to_job(payload)


def _forward_to_mq(job: Job) -> None:
    """Forward the job to the appropriate message queue.

    Args:
        job: The job to forward.
    """
    flavor = labels_to_flavor(
        labels=set(job.labels),
        label_flavor_mapping=app.config["LABEL_FLAVOR_MAPPING"],
    )
    app.logger.info("Received job %s for flavor %s", job.json(), flavor)
    add_job_to_queue(job, flavor)


# Exclude from coverage since unit tests should not run as __main__
if __name__ == "__main__":  # pragma: no cover
    # Start development server
    app.logger.setLevel(logging.DEBUG)
    config_app(app)
    app.run()
