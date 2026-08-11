"""
SEC H-3: the app must refuse to boot on a missing / weak / placeholder
SECRET_KEY in every environment except an explicit test run.

We test the pure ``validate_secret_key`` function directly so we don't have to
re-import the module under different env vars.
"""
import pytest

from auth_config import validate_secret_key, MIN_SECRET_KEY_LEN


STRONG = "x" * MIN_SECRET_KEY_LEN  # exactly at the boundary


def test_missing_key_rejected_even_in_test_mode():
    with pytest.raises(ValueError):
        validate_secret_key("", test_mode=True)
    with pytest.raises(ValueError):
        validate_secret_key("", test_mode=False)


def test_short_key_rejected_in_non_test():
    with pytest.raises(ValueError):
        validate_secret_key("too-short", test_mode=False)


def test_placeholder_key_rejected_in_non_test():
    with pytest.raises(ValueError):
        validate_secret_key(
            "change-me-to-a-random-64-char-string", test_mode=False
        )


def test_strong_key_accepted_in_non_test():
    # Should not raise.
    validate_secret_key(STRONG, test_mode=False)


def test_boundary_length_enforced():
    with pytest.raises(ValueError):
        validate_secret_key("y" * (MIN_SECRET_KEY_LEN - 1), test_mode=False)
    validate_secret_key("y" * MIN_SECRET_KEY_LEN, test_mode=False)


def test_test_mode_relaxes_length_but_not_emptiness():
    # A short deterministic key is fine under test.
    validate_secret_key("short-test-key", test_mode=True)
