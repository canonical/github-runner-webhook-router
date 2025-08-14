#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Flask application which receives GitHub webhooks and logs those."""
import logging
from collections import namedtuple

import yaml
from flask import Flask, request
from pydantic import BaseModel

from webhook_router import router
from webhook_router.parse import Job, ParseError, webhook_to_job
from webhook_router.router import NonForwardableJobError, to_routing_table
from webhook_router.validation import verify_signature

SUPPORTED_GITHUB_EVENT = "workflow_job"
GITHUB_EVENT_HEADER = "X-Github-Event"
WEBHOOK_SIGNATURE_HEADER = "X-Hub-Signature-256"

ValidationResult = namedtuple("ValidationResult", ["is_valid", "msg"])

app = Flask(__name__.split(".", maxsplit=1)[0])


class ConfigError(Exception):
    """Raised when a configuration error occurs."""


class FlavorsConfig(BaseModel):
    """A class to represent the flavors configuration.

    Attributes:
        flavor_list: The list of mapping of flavors to labels.
    """

    flavor_list: list[dict[str, list[str]]]


def config_app(flask_app: Flask) -> None:
    """Configure the application.

    Args:
        flask_app: The Flask application to configure.
    """
    flask_app.config.from_prefixed_env()
    flavors_config = _parse_flavors_config(flask_app.config.get("FLAVOURS", ""))
    default_flavor = _parse_default_flavor_config(flask_app.config.get("DEFAULT_FLAVOUR", ""))
    default_self_hosted_labels = _parse_default_self_hosted_labels_config(
        flask_app.config.get("DEFAULT_SELF_HOSTED_LABELS", "")
    )
    flask_app.config["DEFAULT_SELF_HOSTED_LABELS"] = default_self_hosted_labels
    flavor_labels_mapping_list = [tuple(item.items())[0] for item in flavors_config.flavor_list]
    flask_app.config["ROUTING_TABLE"] = to_routing_table(
        flavor_label_mapping_list=flavor_labels_mapping_list, default_flavor=default_flavor
    )


def _parse_flavors_config(flavors_config_str: str) -> FlavorsConfig:
    """Get the flavor labels mapping.

    Args:
        flavors_config_str: The flavors to get the mapping for.

    Returns:
        The flavor labels mapping.

    Raises:
        ConfigError: If the FLAVOURS config is invalid.
    """
    if not flavors_config_str:
        raise ConfigError("FLAVOURS config is not set!")

    try:
        flavors_config_yaml = yaml.safe_load(flavors_config_str)
    except yaml.YAMLError as exc:
        raise ConfigError("Invalid 'FLAVOURS' config. Invalid yaml.") from exc
    if not isinstance(flavors_config_yaml, list):
        raise ConfigError(
            "Invalid 'FLAVOURS' config. Expected a YAML file with a list at the top level."
        )

    flavors = set()
    for item in flavors_config_yaml:
        if len(item) != 1:
            raise ConfigError(
                f"Invalid 'FLAVOURS' config. Expected a single key-value pair: {item}"
            )
        flavor, _ = tuple(item.items())[0]
        if flavor in flavors:
            raise ConfigError(f"Invalid 'FLAVOURS' config. Duplicate flavour '{flavor}' found.")
        flavors.add(flavor)
    try:
        flavors_config = FlavorsConfig(flavor_list=flavors_config_yaml)
    except ValueError as exc:
        raise ConfigError("Invalid 'FLAVOURS' config. Invalid format.") from exc
    return flavors_config


def _parse_default_flavor_config(default_flavor: str) -> str:
    """Get the default flavor from the config.

    Args:
        default_flavor: The default flavor config.

    Returns:
        The default flavor.

    Raises:
        ConfigError: If the DEFAULT_FLAVOR config is invalid.
    """
    if not (flavor := default_flavor):
        raise ConfigError("DEFAULT_FLAVOUR config is not set!")
    return flavor


def _parse_default_self_hosted_labels_config(default_self_hosted_labels: str) -> set[str]:
    """Get the default labels from the config.

    Args:
        default_self_hosted_labels: The default labels config.

    Returns:
        The default labels.

    Raises:
        ConfigError: If the DEFAULT_SELF_HOSTED_LABELS config is invalid.
    """
    if not (labels := default_self_hosted_labels):
        raise ConfigError("DEFAULT_SELF_HOSTED_LABELS config is not set!")
    return set(labels.split(","))


@app.route("/health", methods=["GET"])
def health_check() -> tuple[str, int]:
    """Health check endpoint.

    Returns:
        A tuple containing an empty string and 200 status code.
    """
    if not router.can_forward():
        return "Router is not ready to forward jobs.", 503
    return "", 200


@app.route("/webhook", methods=["POST"])
def handle_github_webhook() -> tuple[str, int]:
    """Receive a GitHub webhook and append the payload to a file.

    Returns:
        A tuple containing an empty string and 200 status code on success or
        a failure message and 4xx status code.
    """
    if secret := app.config.get("WEBHOOK_SECRET"):
        signature_header = request.headers.get(WEBHOOK_SIGNATURE_HEADER, "")
        validation_result = _validate_signature_header(
            signature_header=signature_header, secret=secret
        )
        if not validation_result.is_valid:
            return validation_result.msg, 403

    event_header = request.headers.get(GITHUB_EVENT_HEADER, "")
    validation_result = _validate_github_event_header(github_event_header=event_header)
    if not validation_result.is_valid:
        return validation_result.msg, 400

    try:
        job = _parse_job()
    except ParseError as exc:
        app.logger.error("Failed to parse webhook payload: %s", exc)
        return str(exc), 400

    app.logger.debug("Parsed job: %s", job)

    return_msg = ""
    try:
        router.forward(job, routing_table=app.config["ROUTING_TABLE"])
    except NonForwardableJobError as exc:
        app.logger.error(str(exc))
        return_msg = "Not able to forward job due to non-matching labels."
    return return_msg, 200


def _validate_signature_header(signature_header: str, secret: str) -> ValidationResult:
    """Validate the webhook signature.

    Args:
        signature_header: The signature header to validate.
        secret: The secret to validate the signature.

    Returns:
        A tuple containing a boolean indicating if the signature is valid and a message
        on failure.
    """
    if not signature_header:
        app.logger.debug(
            "X-Hub-signature-256 header is missing in request from %s", request.origin
        )
        return ValidationResult(is_valid=False, msg="X-Hub-signature-256 header is missing!")

    if not verify_signature(
        payload=request.data, secret_token=secret, signature_header=signature_header
    ):
        app.logger.debug("Signature validation failed in request from %s", request.origin)
        return ValidationResult(is_valid=False, msg="Signature validation failed!")

    return ValidationResult(is_valid=True, msg="")


def _validate_github_event_header(github_event_header: str) -> ValidationResult:
    """Validate the GitHub event header.

    Args:
        github_event_header: The GitHub event header to validate.

    Returns:
        A tuple containing a boolean indicating if the event is valid and a message
        on failure.
    """
    if github_event_header != SUPPORTED_GITHUB_EVENT:
        if github_event_header:
            msg = f"Webhook event {github_event_header} not supported!"
            app.logger.debug(
                "Received not supported webhook event from %s: %s",
                github_event_header,
                request.origin,
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
    return webhook_to_job(payload=payload, ignore_labels=app.config["DEFAULT_SELF_HOSTED_LABELS"])


# Exclude from coverage since unit tests should not run as __main__
if __name__ == "__main__":  # pragma: no cover
    # Start development server
    app.logger.setLevel(logging.DEBUG)
    config_app(app)
    app.run()
