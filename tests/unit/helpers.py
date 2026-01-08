#  Copyright 2026 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Helper functions for the unit tests."""

import hashlib
import hmac


def create_correct_signature(secret: str, payload: bytes) -> str:
    """Create a correct webhook signature.

    Args:
        secret: The secret.
        payload: The payload.

    Returns:
        The correct signature.
    """
    hash_object = hmac.new(secret.encode("utf-8"), msg=payload, digestmod=hashlib.sha256)
    return "sha256=" + hash_object.hexdigest()


def create_incorrect_signature(secret: str, payload: bytes) -> str:
    """Create an incorrect webhook signature.

    Args:
        secret: The secret.
        payload: The payload.

    Returns:
        The incorrect signature.
    """
    return create_correct_signature(secret, payload)[:-1]
