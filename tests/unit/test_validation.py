#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""The unit tests for the validation module."""
import pytest

from src.validation import SignatureValidationError, verify_signature

# Test secrets are not a security issue.
TEST_SECRET = "It's a Secret to Everybody"  # nosec
TEST_PAYLOAD = b"Hello, World!"


def test_verify_signature_match():
    """
    arrange: A payload, a secret, and a correct signature.
    act: verify the signature.
    assert: No exception is raised.
    """
    expected_sig = "sha256=757107ea0eb2509fc211221cce984b8a37570b6d7586c22c46f4379c8b043e17"

    verify_signature(TEST_PAYLOAD, TEST_SECRET, expected_sig)


def test_verify_signature_mismatch():
    """
    arrange: A payload, a secret, and an invalid signature.
    act: verify the signature.
    assert: A SignatureValidationError is raised.
    """
    expected_sig = "sha256=757107ea0eb2509fc211221cce984b8a37570b6d7586c22c46f4379c8b043e18"

    with pytest.raises(SignatureValidationError):
        verify_signature(TEST_PAYLOAD, TEST_SECRET, expected_sig)
