import time

from fastapi import HTTPException

from core.config import ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_MINUTES
from core.jwt_utils import JWTUtil, JWTError, JWTExpiredError
from core.password import PasswordHasher
from users.repository import UserRepository


class AuthService:
    def __init__(self, user_repo: UserRepository, kv, jwt_secret: str):
        self.user_repo = user_repo
        self.kv = kv
        self.jwt_secret = jwt_secret

    async def register(self, username: str, email: str, password: str) -> dict:
        """Register a new user. Returns user info dict."""
        existing = await self.user_repo.get_by_email(email)
        if existing:
            raise HTTPException(status_code=409, detail="该邮箱已被注册")

        existing = await self.user_repo.get_by_username(username)
        if existing:
            raise HTTPException(status_code=409, detail="该用户名已被占用")

        password_hash = PasswordHasher.hash_password(password)
        user = await self.user_repo.create_user(username, email, password_hash)
        # Re-query to get DB-generated created_at
        full_user = await self.user_repo.get_by_id(user["id"])
        return {
            "id": full_user["id"],
            "username": full_user["username"],
            "email": full_user["email"],
            "role": full_user["role"],
            "created_at": full_user["created_at"],
        }

    async def login(self, email: str, password: str) -> dict:
        """Authenticate user and return tokens."""
        user = await self.user_repo.get_by_email(email)
        if not user or not user.get("password_hash"):
            raise HTTPException(status_code=401, detail="凭据无效")

        if not PasswordHasher.verify_password(password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="凭据无效")

        payload = {
            "sub": user["id"],
            "username": user["username"],
            "role": user["role"],
            "type": "access",
        }
        access_token = JWTUtil.create_token(payload, self.jwt_secret, ACCESS_TOKEN_EXPIRE_MINUTES)

        refresh_payload = {
            "sub": user["id"],
            "username": user["username"],
            "role": user["role"],
            "type": "refresh",
        }
        refresh_token = JWTUtil.create_token(refresh_payload, self.jwt_secret, REFRESH_TOKEN_EXPIRE_MINUTES)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user_id": user["id"],
        }

    async def refresh_token(self, refresh_token_str: str) -> dict:
        """Validate refresh token and return new token pair."""
        try:
            payload = JWTUtil.decode_token(refresh_token_str, self.jwt_secret)
        except JWTExpiredError:
            raise HTTPException(status_code=401, detail="刷新令牌无效")
        except JWTError:
            raise HTTPException(status_code=401, detail="刷新令牌无效")

        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="刷新令牌无效")

        if await JWTUtil.is_blacklisted(refresh_token_str, self.kv):
            raise HTTPException(status_code=401, detail="令牌已失效")

        user_id = payload.get("sub")
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=401, detail="刷新令牌无效")

        new_access_payload = {
            "sub": user["id"],
            "username": user["username"],
            "role": user["role"],
            "type": "access",
        }
        new_access_token = JWTUtil.create_token(new_access_payload, self.jwt_secret, ACCESS_TOKEN_EXPIRE_MINUTES)

        new_refresh_payload = {
            "sub": user["id"],
            "username": user["username"],
            "role": user["role"],
            "type": "refresh",
        }
        new_refresh_token = JWTUtil.create_token(new_refresh_payload, self.jwt_secret, REFRESH_TOKEN_EXPIRE_MINUTES)

        # Blacklist the old refresh token
        old_exp = payload.get("exp", 0)
        remaining_ttl = max(old_exp - int(time.time()), 0)
        if remaining_ttl > 0:
            await JWTUtil.blacklist_token(refresh_token_str, self.kv, remaining_ttl)

        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
        }

    async def logout(self, access_token: str, refresh_token_str: str) -> None:
        """Blacklist both tokens."""
        now = int(time.time())

        # Blacklist access token
        try:
            access_payload = JWTUtil.decode_token(access_token, self.jwt_secret)
            access_ttl = max(access_payload.get("exp", 0) - now, 0)
            if access_ttl > 0:
                await JWTUtil.blacklist_token(access_token, self.kv, access_ttl)
        except (JWTError, JWTExpiredError):
            pass  # Token already expired or invalid, no need to blacklist

        # Blacklist refresh token
        try:
            refresh_payload = JWTUtil.decode_token(refresh_token_str, self.jwt_secret)
            refresh_ttl = max(refresh_payload.get("exp", 0) - now, 0)
            if refresh_ttl > 0:
                await JWTUtil.blacklist_token(refresh_token_str, self.kv, refresh_ttl)
        except (JWTError, JWTExpiredError):
            pass
