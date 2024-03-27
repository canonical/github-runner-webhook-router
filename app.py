#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""The main entry point for the webhook router used by the rock."""
import logging

# The rock expects an app.py file with a flask app named app.

from webhook_router.app import app

# the charm will run this file with gunicorn, so we need to set up logging
# we use the gunicorn logger to ensure that logs are captured and transmitted to loki
gunicorn_logger = logging.getLogger('gunicorn.error')
app.logger.handlers = gunicorn_logger.handlers
app.logger.setLevel(gunicorn_logger.level)
