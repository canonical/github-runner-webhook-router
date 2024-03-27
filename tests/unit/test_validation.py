#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""The unit tests for the validation module."""
import secrets
from typing import Callable

import pytest

from src.validation import verify_signature
from tests.unit.helpers import create_correct_signature, create_incorrect_signature


@pytest.mark.parametrize(
    "create_signature_fct, expected_return_value",
    [
        pytest.param(
            create_correct_signature,
            True,
            id="correct signature",
        ),
        pytest.param(
            create_incorrect_signature,
            False,
            id="incorrect signature",
        ),
    ],
)
def test_verify_signature(
    create_signature_fct: Callable[[str, bytes], str], expected_return_value: bool
):
    """
    arrange: A payload, a secret, and a signature.
    act: Verify the signature.
    assert: The expected return value is returned.
    """
    secret = secrets.token_hex(16)
    payload = secrets.token_bytes(16)
    expected_sig = create_signature_fct(secret, payload)

    assert verify_signature(payload, secret, expected_sig) is expected_return_value
