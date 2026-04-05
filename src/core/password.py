import hashlib
import os


class PasswordHasher:
    ITERATIONS = 100_000

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using PBKDF2-SHA256 with random salt. Returns 'salt_hex$hash_hex'."""
        salt = os.urandom(16)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PasswordHasher.ITERATIONS)
        return f"{salt.hex()}${dk.hex()}"

    @staticmethod
    def verify_password(password: str, stored_hash: str) -> bool:
        """Verify password against stored 'salt_hex$hash_hex' hash."""
        try:
            salt_hex, hash_hex = stored_hash.split("$", 1)
            salt = bytes.fromhex(salt_hex)
            dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PasswordHasher.ITERATIONS)
            return dk.hex() == hash_hex
        except (ValueError, AttributeError):
            return False
