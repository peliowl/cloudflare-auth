import base64
import hashlib
import hmac
import json
import time
import uuid


class JWTError(Exception):
    pass


class JWTExpiredError(JWTError):
    pass


class JWTUtil:
    @staticmethod
    def _b64url_encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    @staticmethod
    def _b64url_decode(s: str) -> bytes:
        padding = 4 - len(s) % 4
        if padding != 4:
            s += "=" * padding
        return base64.urlsafe_b64decode(s)

    @staticmethod
    def create_token(payload: dict, secret: str, expires_minutes: int) -> str:
        """Generate a JWT token (HS256)."""
        header = {"alg": "HS256", "typ": "JWT"}
        now = int(time.time())
        token_payload = {
            **payload,
            "iat": now,
            "exp": now + expires_minutes * 60,
            "jti": str(uuid.uuid4()),
        }

        header_b64 = JWTUtil._b64url_encode(json.dumps(header, separators=(",", ":")).encode())
        payload_b64 = JWTUtil._b64url_encode(json.dumps(token_payload, separators=(",", ":")).encode())
        signing_input = f"{header_b64}.{payload_b64}"
        signature = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
        sig_b64 = JWTUtil._b64url_encode(signature)
        return f"{signing_input}.{sig_b64}"

    @staticmethod
    def decode_token(token: str, secret: str) -> dict:
        """Decode and verify a JWT token. Raises JWTError or JWTExpiredError on failure."""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                raise JWTError("令牌无效")

            header_b64, payload_b64, sig_b64 = parts
            signing_input = f"{header_b64}.{payload_b64}"
            expected_sig = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
            actual_sig = JWTUtil._b64url_decode(sig_b64)

            if not hmac.compare_digest(expected_sig, actual_sig):
                raise JWTError("令牌无效")

            payload = json.loads(JWTUtil._b64url_decode(payload_b64))

            if "exp" in payload and payload["exp"] < int(time.time()):
                raise JWTExpiredError("令牌已过期")

            return payload
        except (JWTError, JWTExpiredError):
            raise
        except Exception:
            raise JWTError("令牌无效")

    @staticmethod
    async def is_blacklisted(token: str, kv) -> bool:
        """Check if a token is blacklisted in KV store."""
        try:
            payload = token.split(".")[1]
            decoded = json.loads(JWTUtil._b64url_decode(payload))
            jti = decoded.get("jti", "")
        except Exception:
            jti = token
        result = await kv.get(f"blacklist:{jti}")
        # KV.get() returns JS null for missing keys. In Pyodide, JS null
        # becomes pyodide.ffi.jsnull (not Python None). A found value is a
        # JS string which is truthy. Both None and jsnull are falsy.
        if result is None:
            return False
        try:
            # pyodide.ffi.jsnull is falsy
            return bool(result)
        except Exception:
            return False

    @staticmethod
    async def blacklist_token(token: str, kv, ttl_seconds: int) -> None:
        """Add a token to the blacklist in KV store."""
        try:
            payload = token.split(".")[1]
            decoded = json.loads(JWTUtil._b64url_decode(payload))
            jti = decoded.get("jti", "")
        except Exception:
            jti = token
        if ttl_seconds > 0:
            await kv.put(f"blacklist:{jti}", "1", expiration_ttl=ttl_seconds)
