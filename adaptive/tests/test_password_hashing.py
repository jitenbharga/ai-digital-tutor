"""
SEC C-1 regression guard.

`security.py` builds its hasher with `PasswordHash.recommended()`, which requires
the Argon2 backend (and Bcrypt for legacy verification). If `requirements.txt`
ever drops the `pwdlib[argon2,bcrypt]` extras again, a clean install raises
`pwdlib.exceptions.HasherNotAvailable` and every signup/login breaks.

These tests exercise the REAL hasher (no mock) so the suite fails loudly on a
broken install instead of shipping unauthenticatable users to production.
"""
import pytest


def test_argon2_backend_is_available():
    """The recommended hasher must construct without HasherNotAvailable."""
    from pwdlib import PasswordHash

    hasher = PasswordHash.recommended()
    assert hasher is not None


def test_hash_and_verify_roundtrip():
    """A hashed password verifies; a wrong password does not."""
    from security import hash_password, verify_password

    password = "C0rrect-Horse-Battery-Staple!"
    hashed = hash_password(password)

    # A real hash: non-empty, not the plaintext, and looks like a PHC string.
    assert hashed
    assert hashed != password
    assert hashed.startswith("$"), "expected a PHC-formatted hash (argon2/bcrypt)"

    assert verify_password(password, hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_hashes_are_salted_and_unique():
    """Two hashes of the same password differ (per-hash salt)."""
    from security import hash_password, verify_password

    p = "same-password-123"
    h1 = hash_password(p)
    h2 = hash_password(p)
    assert h1 != h2
    assert verify_password(p, h1) and verify_password(p, h2)
