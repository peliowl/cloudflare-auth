from fastapi import APIRouter, Depends, Request

import asgi
from auth.dependencies import get_current_user
from auth.models import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from auth.service import AuthService
from users.repository import UserRepository
from users.login_history_repository import LoginHistoryRepository

auth_router = APIRouter(prefix="/auth", tags=["auth"])


def _build_service(env) -> AuthService:
    repo = UserRepository(env.DB)
    return AuthService(repo, env.TOKEN_BLACKLIST, env.JWT_SECRET)


def _extract_request_info(request: Request, env=None) -> dict:
    """Extract IP, geo info, and user-agent from the request."""
    ip = request.headers.get("cf-connecting-ip")
    user_agent = request.headers.get("user-agent")
    # asgi 模块的 request_to_scope 不会将 cf 对象传入 ASGI scope，
    # 因此通过 env._cf 获取（在 main.py 的 Default.fetch 中挂载）
    cf = getattr(env, '_cf', None) if env else None
    country = city = region = None
    if cf:
        def _get(obj, key):
            try:
                val = getattr(obj, key, None)
                if val is None:
                    return None
                s = str(val)
                return None if s in ("undefined", "null", "") else s
            except Exception:
                return None
        country = _get(cf, "country")
        city = _get(cf, "city")
        region = _get(cf, "region")
    return {"ip": ip, "country": country, "city": city, "region": region, "user_agent": user_agent}


@auth_router.post("/register", response_model=UserResponse)
async def register(body: RegisterRequest, env=asgi.env):
    service = _build_service(env)
    user = await service.register(body.username, body.email, body.password)
    return user


@auth_router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request, env=asgi.env):
    service = _build_service(env)
    tokens = await service.login(body.email, body.password)
    # Record login history
    info = _extract_request_info(request, env)
    history_repo = LoginHistoryRepository(env.DB)
    await history_repo.create_record(
        user_id=tokens["user_id"],
        action="login",
        method="password",
        ip=info["ip"],
        country=info["country"],
        city=info["city"],
        region=info["region"],
        user_agent=info["user_agent"],
    )
    return tokens


@auth_router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, env=asgi.env):
    service = _build_service(env)
    tokens = await service.refresh_token(body.refresh_token)
    return tokens


@auth_router.post("/logout")
async def logout(
    body: RefreshRequest,
    request: Request,
    env=asgi.env,
    current_user: dict = Depends(get_current_user),
):
    service = _build_service(env)
    await service.logout(current_user["token"], body.refresh_token)
    # Record logout history
    info = _extract_request_info(request, env)
    history_repo = LoginHistoryRepository(env.DB)
    await history_repo.create_record(
        user_id=current_user["id"],
        action="logout",
        method=None,
        ip=info["ip"],
        country=info["country"],
        city=info["city"],
        region=info["region"],
        user_agent=info["user_agent"],
    )
    return {"detail": "已成功注销"}
