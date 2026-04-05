"""Tests for Pydantic request/response models."""
import pytest
from pydantic import ValidationError
from auth.models import RegisterRequest, LoginRequest, TokenResponse, UserResponse


class TestRegisterRequest:
    def test_valid_registration(self):
        req = RegisterRequest(username="alice", email="alice@example.com", password="password123")
        assert req.username == "alice"
        assert req.email == "alice@example.com"
        assert req.password == "password123"

    def test_short_password_rejected(self):
        with pytest.raises(ValidationError):
            RegisterRequest(username="alice", email="alice@example.com", password="short")

    def test_password_min_length_boundary(self):
        # Exactly 8 chars should pass
        req = RegisterRequest(username="alice", email="alice@example.com", password="12345678")
        assert req.password == "12345678"

        # 7 chars should fail
        with pytest.raises(ValidationError):
            RegisterRequest(username="alice", email="alice@example.com", password="1234567")

    def test_invalid_email_rejected(self):
        with pytest.raises(ValidationError):
            RegisterRequest(username="alice", email="not-an-email", password="password123")

    def test_email_normalized_to_lowercase(self):
        req = RegisterRequest(username="alice", email="Alice@Example.COM", password="password123")
        assert req.email == "alice@example.com"

    def test_empty_username_rejected(self):
        with pytest.raises(ValidationError):
            RegisterRequest(username="", email="alice@example.com", password="password123")


class TestLoginRequest:
    def test_valid_login(self):
        req = LoginRequest(email="alice@example.com", password="password123")
        assert req.email == "alice@example.com"

    def test_invalid_email_rejected(self):
        with pytest.raises(ValidationError):
            LoginRequest(email="bad-email", password="password123")


class TestTokenResponse:
    def test_default_token_type(self):
        resp = TokenResponse(access_token="at", refresh_token="rt")
        assert resp.token_type == "bearer"


class TestUserResponse:
    def test_all_fields_present(self):
        resp = UserResponse(id="1", username="alice", email="a@b.com", role="user", created_at="2025-01-01")
        assert resp.id == "1"
        assert resp.role == "user"
