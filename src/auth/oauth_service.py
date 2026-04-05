import json
import os
import time
import base64
from urllib.parse import urlencode

from fastapi import HTTPException

from core.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_MINUTES,
    OAUTH_PROVIDERS,
    OAUTH_STATE_TTL,
)
from core.jwt_utils import JWTUtil
from users.repository import UserRepository


class OAuthService:
    def __init__(self, user_repo: UserRepository, kv, jwt_secret: str, env):
        self.user_repo = user_repo
        self.kv = kv
        self.jwt_secret = jwt_secret
        self.env = env

    async def get_authorization_url(self, provider: str, redirect_uri: str) -> str:
        """Generate OAuth authorization URL with state stored in KV.
        Returns the full authorization URL to redirect the user to."""
        if provider not in OAUTH_PROVIDERS:
            raise HTTPException(status_code=400, detail="不支持的登录方式")

        config = OAUTH_PROVIDERS[provider]
        state = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode("ascii")

        # Build KV value - store provider info
        kv_data = {"provider": provider, "created_at": int(time.time())}

        params = {
            "client_id": self._get_client_id(provider),
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": config["scope"],
            "state": state,
            "prompt": "select_account",
        }

        # Store state in KV with TTL
        await self.kv.put(
            f"oauth_state:{state}",
            json.dumps(kv_data),
            expiration_ttl=OAUTH_STATE_TTL,
        )

        authorization_url = f"{config['authorize_url']}?{urlencode(params)}"
        return authorization_url

    async def handle_callback(self, provider: str, code: str, state: str, redirect_uri: str) -> dict:
        """Handle OAuth callback: verify state -> exchange code -> get user info -> find/create user -> return JWT tokens."""
        if provider not in OAUTH_PROVIDERS:
            raise HTTPException(status_code=400, detail="不支持的登录方式")

        # Verify state from KV
        state_data_raw = await self.kv.get(f"oauth_state:{state}")
        if state_data_raw is None or not state_data_raw:
            raise HTTPException(status_code=400, detail="授权请求无效或已过期")

        try:
            state_data_str = str(state_data_raw)
            state_data = json.loads(state_data_str)
        except Exception:
            raise HTTPException(status_code=400, detail="授权请求无效或已过期")

        if state_data.get("provider") != provider:
            raise HTTPException(status_code=400, detail="授权请求无效或已过期")

        # Delete used state to prevent replay
        await self.kv.delete(f"oauth_state:{state}")

        # Exchange code for access token
        token_data = await self._exchange_code(provider, code, redirect_uri)
        oauth_access_token = token_data["access_token"]
        oauth_expires_in = token_data["expires_in"]  # seconds, typically 3600 for Google

        # Get user info from provider
        user_info = await self._get_user_info(provider, oauth_access_token)

        # Calculate access_token_expires_at from expires_in
        access_token_expires_at = None
        if oauth_expires_in:
            access_token_expires_at = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(time.time()) + oauth_expires_in)
            )

        # Find or create user
        user = await self._find_or_create_user(
            provider,
            user_info["provider_user_id"],
            user_info["email"],
            user_info["name"],
            user_info.get("avatar_url"),
            access_token_expires_at,
        )

        # Use Google's expires_in for access_token expiration (default to system config if not available)
        access_expire_minutes = ACCESS_TOKEN_EXPIRE_MINUTES
        if oauth_expires_in:
            access_expire_minutes = oauth_expires_in // 60  # Convert seconds to minutes

        # Generate JWT tokens
        access_payload = {
            "sub": user["id"],
            "username": user["username"],
            "role": user["role"],
            "type": "access",
        }
        access_token = JWTUtil.create_token(access_payload, self.jwt_secret, access_expire_minutes)

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

    async def _exchange_code(self, provider: str, code: str, redirect_uri: str) -> dict:
        """Exchange authorization code for access token using fetch API.
        Returns dict with access_token and expires_in."""
        from js import fetch, Headers

        config = OAUTH_PROVIDERS[provider]
        token_url = config["token_url"]

        body_params = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self._get_client_id(provider),
            "client_secret": self._get_client_secret(provider),
        }

        headers = Headers.new()
        headers.set("Content-Type", "application/x-www-form-urlencoded")
        headers.set("Accept", "application/json")

        response = await fetch(
            token_url,
            method="POST",
            headers=headers,
            body=urlencode(body_params),
        )

        if not response.ok:
            raise HTTPException(status_code=502, detail="第三方登录服务暂时不可用")

        data = await response.json()
        access_token = data.access_token
        if not access_token:
            raise HTTPException(status_code=502, detail="第三方登录服务暂时不可用")

        # Extract expires_in (Google typically returns 3600 seconds = 1 hour)
        expires_in = None
        try:
            raw = data.expires_in
            if raw is not None and str(raw) not in ("undefined", "null", ""):
                expires_in = int(str(raw))
        except Exception:
            pass

        return {"access_token": str(access_token), "expires_in": expires_in}

    async def _get_user_info(self, provider: str, access_token: str) -> dict:
        """Fetch user info (email, name) from OAuth provider."""
        from js import fetch, Headers

        config = OAUTH_PROVIDERS[provider]
        userinfo_url = config["userinfo_url"]

        headers = Headers.new()
        headers.set("Authorization", f"Bearer {access_token}")
        headers.set("Accept", "application/json")

        response = await fetch(userinfo_url, method="GET", headers=headers)

        if not response.ok:
            raise HTTPException(status_code=502, detail="无法获取第三方账号信息")

        data = await response.json()

        if provider == "google":
            # Extract avatar URL (picture field from Google)
            avatar_url = None
            try:
                raw = data.picture
                if raw is not None and str(raw) not in ("undefined", "null", ""):
                    avatar_url = str(raw)
            except Exception:
                pass

            return {
                "email": str(data.email),
                "name": str(data.name or data.email.split("@")[0]),
                "provider_user_id": str(data.id),
                "avatar_url": avatar_url,
            }

        raise HTTPException(status_code=400, detail="不支持的登录方式")

    async def _find_or_create_user(self, provider: str, provider_user_id: str, email: str, name: str,
                                    avatar_url: str = None, access_token_expires_at: str = None) -> dict:
        """Find existing user by OAuth account or email, or create a new one."""
        # Check if OAuth account already exists
        existing_oauth = await self.user_repo.get_oauth_account(provider, provider_user_id)
        if existing_oauth:
            # Update OAuth account info on each login
            await self.user_repo.update_oauth_account(
                provider, provider_user_id,
                provider_email=email,
                provider_name=name,
                provider_avatar_url=avatar_url,
                access_token_expires_at=access_token_expires_at,
            )
            return {
                "id": existing_oauth["id"],
                "username": existing_oauth["username"],
                "email": existing_oauth["email"],
                "role": existing_oauth["role"],
            }

        # Check if a user with this email already exists
        existing_user = await self.user_repo.get_by_email(email)
        if existing_user:
            # Link OAuth account to existing user
            await self.user_repo.create_oauth_account(
                existing_user["id"], provider, provider_user_id,
                provider_email=email,
                provider_name=name,
                provider_avatar_url=avatar_url,
                access_token_expires_at=access_token_expires_at,
            )
            return {
                "id": existing_user["id"],
                "username": existing_user["username"],
                "email": existing_user["email"],
                "role": existing_user["role"],
            }

        # Create new user without password
        # Ensure username uniqueness by appending random suffix if needed
        username = name
        existing_name = await self.user_repo.get_by_username(username)
        if existing_name:
            suffix = base64.urlsafe_b64encode(os.urandom(4)).rstrip(b"=").decode("ascii")
            username = f"{name}_{suffix}"

        user = await self.user_repo.create_user_without_password(username, email)

        # Link OAuth account
        await self.user_repo.create_oauth_account(
            user["id"], provider, provider_user_id,
            provider_email=email,
            provider_name=name,
            provider_avatar_url=avatar_url,
            access_token_expires_at=access_token_expires_at,
        )

        return {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "role": user["role"],
        }

    def _get_client_id(self, provider: str) -> str:
        if provider == "google":
            return str(self.env.GOOGLE_CLIENT_ID)
        return ""

    def _get_client_secret(self, provider: str) -> str:
        if provider == "google":
            return str(self.env.GOOGLE_CLIENT_SECRET)
        return ""
