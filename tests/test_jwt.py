"""Tests for JWT utility module."""
import time
from core.jwt_utils import JWTUtil, JWTError, JWTExpiredError


SECRET = "test-secret-key-for-jwt"


class TestJWTUtil:
    def test_create_and_decode_roundtrip(self):
        payload = {"sub": "user123", "username": "alice", "role": "user"}
        token = JWTUtil.create_token(payload, SECRET, expires_minutes=15)
        decoded = JWTUtil.decode_token(token, SECRET)
        assert decoded["sub"] == "user123"
        assert decoded["username"] == "alice"
        assert decoded["role"] == "user"
        assert "exp" in decoded
        assert "iat" in decoded
        assert "jti" in decoded

    def test_token_has_three_parts(self):
        token = JWTUtil.create_token({"sub": "u1"}, SECRET, expires_minutes=5)
        assert len(token.split(".")) == 3

    def test_decode_with_wrong_secret_raises(self):
        token = JWTUtil.create_token({"sub": "u1"}, SECRET, expires_minutes=5)
        try:
            JWTUtil.decode_token(token, "wrong-secret")
            assert False, "Should have raised JWTError"
        except JWTError:
            pass

    def test_decode_expired_token_raises(self):
        token = JWTUtil.create_token({"sub": "u1"}, SECRET, expires_minutes=-1)
        try:
            JWTUtil.decode_token(token, SECRET)
            assert False, "Should have raised JWTExpiredError"
        except JWTExpiredError:
            pass

    def test_decode_malformed_token_raises(self):
        for bad_token in ["not.a.jwt", "abc", "", "a.b.c"]:
            try:
                JWTUtil.decode_token(bad_token, SECRET)
                assert False, f"Should have raised JWTError for '{bad_token}'"
            except JWTError:
                pass

    def test_expiration_is_correct(self):
        before = int(time.time())
        token = JWTUtil.create_token({"sub": "u1"}, SECRET, expires_minutes=15)
        decoded = JWTUtil.decode_token(token, SECRET)
        after = int(time.time())
        expected_min = before + 15 * 60
        expected_max = after + 15 * 60
        assert expected_min <= decoded["exp"] <= expected_max

    def test_each_token_has_unique_jti(self):
        t1 = JWTUtil.create_token({"sub": "u1"}, SECRET, expires_minutes=5)
        t2 = JWTUtil.create_token({"sub": "u1"}, SECRET, expires_minutes=5)
        d1 = JWTUtil.decode_token(t1, SECRET)
        d2 = JWTUtil.decode_token(t2, SECRET)
        assert d1["jti"] != d2["jti"]
