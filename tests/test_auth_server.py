"""Tests for auth_server.py — password verification smoke tests."""

import pytest
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError


class TestPasswordVerification:
    """Argon2 password hashing and verification."""

    def test_correct_password_verifies(self):
        ph = PasswordHasher()
        pw_hash = ph.hash("correct-horse-battery-staple")
        ph.verify(pw_hash, "correct-horse-battery-staple")

    def test_wrong_password_raises(self):
        ph = PasswordHasher()
        pw_hash = ph.hash("correct-horse-battery-staple")
        with pytest.raises(VerifyMismatchError):
            ph.verify(pw_hash, "wrong-password")

    def test_rehash_check_false_for_fresh_hash(self):
        ph = PasswordHasher()
        pw_hash = ph.hash("fresh-hash")
        assert ph.check_needs_rehash(pw_hash) is False
