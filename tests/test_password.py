"""Tests for password hashing module."""
from core.password import PasswordHasher


class TestPasswordHasher:
    def test_hash_returns_salt_dollar_hash_format(self):
        result = PasswordHasher.hash_password("testpass123")
        parts = result.split("$")
        assert len(parts) == 2
        # salt is 16 bytes = 32 hex chars
        assert len(parts[0]) == 32
        # SHA-256 hash is 32 bytes = 64 hex chars
        assert len(parts[1]) == 64

    def test_verify_correct_password(self):
        password = "mySecurePass1"
        hashed = PasswordHasher.hash_password(password)
        assert PasswordHasher.verify_password(password, hashed) is True

    def test_verify_wrong_password(self):
        hashed = PasswordHasher.hash_password("correctPassword")
        assert PasswordHasher.verify_password("wrongPassword", hashed) is False

    def test_different_hashes_for_same_password(self):
        password = "samePassword123"
        h1 = PasswordHasher.hash_password(password)
        h2 = PasswordHasher.hash_password(password)
        assert h1 != h2
        # Both should still verify
        assert PasswordHasher.verify_password(password, h1) is True
        assert PasswordHasher.verify_password(password, h2) is True

    def test_verify_malformed_hash_returns_false(self):
        assert PasswordHasher.verify_password("test", "not-a-valid-hash") is False
        assert PasswordHasher.verify_password("test", "") is False

    def test_empty_password(self):
        hashed = PasswordHasher.hash_password("")
        assert PasswordHasher.verify_password("", hashed) is True
        assert PasswordHasher.verify_password("notempty", hashed) is False
