#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""The main entry point for the webhook router used by the rock."""

# The rock expects an app.py file with a flask app named app.

from webhook_router.app import app
