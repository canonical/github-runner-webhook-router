#  Copyright 2026 Canonical Ltd.
#  See LICENSE file for licensing details.

"""The main entry point for the charmed webhook router."""
import logging
import os


class ConfigError(Exception):
    """Raised when a configuration error occurs."""


class IntegrationMissingError(Exception):
    """Raised when an integration is missing."""


def _set_up_logging() -> None:
    """Set up logging.

    Raises:
        ConfigError: If the log level is invalid.
    """
    root_logger = logging.getLogger()
    _set_log_handlers(root_logger)
    _set_log_level(root_logger)


def _set_log_handlers(logger: logging.Logger) -> None:
    """Set the log handlers for the particular logging.

    Args:
        app: The Flask application.
    """
    # we use the gunicorn logger to ensure that logs are captured and transmitted to loki
    gunicorn_logger = logging.getLogger('gunicorn.error')
    logger.handlers = gunicorn_logger.handlers


def _set_log_level(logger: logging.Logger) -> None:
    """Set the log level of the application.

    Args:
        app: The Flask application.

    Raises:
        ConfigError: If the log level is invalid.
    """
    level_name_mapping = {
        'CRITICAL': logging.CRITICAL,
        'FATAL': logging.FATAL,
        'ERROR': logging.ERROR,
        'WARN': logging.WARNING,
        'WARNING': logging.WARNING,
        'INFO': logging.INFO,
        'DEBUG': logging.DEBUG,
        'NOTSET': logging.NOTSET,
    }
    level_name = os.environ.get("FLASK_LOG_LEVEL", "INFO")
    try:
        level = level_name_mapping[level_name]
    except KeyError:
        raise ConfigError(f"Invalid log level: {level_name}")
    logger.setLevel(level)


# the charm will run this file with gunicorn, so we need to set up logging
_set_up_logging()

if os.environ.get("MONGODB_DB_CONNECT_STRING") is None:
    raise IntegrationMissingError("mongodb integration is missing")

# The charm sets up gunicorn to use an app.py file with a flask app named app.
from webhook_router.app import app, config_app, ConfigError as AppConfigError

try:
    config_app(app)
except AppConfigError as exc:
    raise ConfigError(f"Invalid app config: {exc}") from exc
