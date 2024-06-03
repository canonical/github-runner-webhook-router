#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""The main entry point for the charmed webhook router."""
import logging

from flask import Flask

# The charm sets up gunicorn to use an app.py file with a flask app named app.
from webhook_router.app import app


class ConfigError(Exception):
    """Raised when a configuration error occurs."""

    pass


def _set_up_logging(app: Flask) -> None:
    """Set up logging for the application.

    Raises:
        ConfigError: If the log level is invalid.
    """
    _set_log_handlers(app)
    _set_log_level(app)


def _set_log_handlers(app: Flask) -> None:
    """Set the log handlers of the application.

    Args:
        app: The Flask application.
    """
    # we use the gunicorn logger to ensure that logs are captured and transmitted to loki
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers


def _set_log_level(app: Flask) -> None:
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
    try:
        level = level_name_mapping[app.config.get("LOG_LEVEL", "INFO")]
    except KeyError:
        raise ConfigError(f"Invalid log level: {app.config.get('LOG_LEVEL')}")
    app.logger.setLevel(level)


# the charm will run this file with gunicorn, so we need to set up logging
_set_up_logging(app)
