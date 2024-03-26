#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module for validating the webhook request."""

import hashlib
import hmac


def verify_signature(payload: bytes, secret_token: str, signature_header: str) -> bool:
    """Verify that the payload was sent from GitHub by validating SHA256.

    Raise error if the signature doesn't match.

    Args:
        payload: original request body to verify
        secret_token: GitHub app webhook token (WEBHOOK_SECRET)
        signature_header: header received from GitHub (x-hub-signature-256)

    Returns:
        True if the signature is valid, False otherwise.
    """
    hash_object = hmac.new(secret_token.encode("utf-8"), msg=payload, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()
    return hmac.compare_digest(expected_signature, signature_header)
