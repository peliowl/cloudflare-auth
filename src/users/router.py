from fastapi import APIRouter, Depends, HTTPException, Query, Request

import asgi
from auth.dependencies import get_current_user
from auth.models import UserResponse, GeoResponse, UserDetailResponse, SetPasswordRequest, OAuthAccountInfo, LoginHistoryResponse, LoginHistoryRecord
from core.password import PasswordHasher
from users.repository import UserRepository
from users.login_history_repository import LoginHistoryRepository

users_router = APIRouter(prefix="/users", tags=["users"])


@users_router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user), env=asgi.env):
    """获取当前用户基本信息（用户名、邮箱、角色、注册时间）"""
    repo = UserRepository(env.DB)
    user = await repo.get_by_id(current_user["id"])
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="用户不存在")
    return UserResponse(
        id=user["id"],
        username=user["username"],
        email=user["email"],
        role=user["role"],
        created_at=user["created_at"],
    )


@users_router.get("/me/geo", response_model=GeoResponse)
async def get_my_geo(request: Request, current_user: dict = Depends(get_current_user), env=asgi.env):
    """获取当前用户的 IP 地址和地理位置信息"""
    ip = request.headers.get("cf-connecting-ip", "unknown")

    # asgi 模块的 request_to_scope 不会将 cf 对象传入 ASGI scope，
    # 因此通过 env._cf 获取（在 main.py 的 Default.fetch 中挂载）
    cf = getattr(env, '_cf', None)

    country = None
    city = None
    region = None
    latitude = None
    longitude = None
    timezone = None

    if cf:
        # cf 是 Pyodide 中的 JS 代理对象，使用属性访问读取字段
        # 对于 JS undefined 值，转换为 Python None
        def _get(obj, key):
            try:
                val = getattr(obj, key, None)
                # JS undefined/null 在 Pyodide 中可能表现为特殊值
                if val is None:
                    return None
                s = str(val)
                if s in ("undefined", "null", ""):
                    return None
                return s
            except Exception:
                return None

        country = _get(cf, "country")
        city = _get(cf, "city")
        region = _get(cf, "region")
        latitude = _get(cf, "latitude")
        longitude = _get(cf, "longitude")
        timezone = _get(cf, "timezone")

    return GeoResponse(
        ip=ip,
        country=country,
        city=city,
        region=region,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone,
    )


@users_router.get("/me/detail", response_model=UserDetailResponse)
async def get_my_detail(current_user: dict = Depends(get_current_user), env=asgi.env):
    """获取当前用户详细信息，包括是否已设置密码和关联的 OAuth 账号列表"""
    repo = UserRepository(env.DB)
    user = await repo.get_by_id(current_user["id"])
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    oauth_accounts_raw = await repo.get_oauth_accounts_by_user(current_user["id"])
    oauth_accounts = [
        OAuthAccountInfo(
            provider=oa.get("provider", ""),
            provider_user_id=oa.get("provider_user_id", ""),
            provider_email=oa.get("provider_email"),
            provider_name=oa.get("provider_name"),
            provider_avatar_url=oa.get("provider_avatar_url"),
            created_at=oa.get("created_at", ""),
        )
        for oa in oauth_accounts_raw
    ]

    return UserDetailResponse(
        id=user["id"],
        username=user["username"],
        email=user["email"],
        role=user["role"],
        created_at=user["created_at"],
        has_password=bool(user.get("password_hash")),
        oauth_accounts=oauth_accounts,
    )


@users_router.put("/me/password")
async def set_password(body: SetPasswordRequest, current_user: dict = Depends(get_current_user), env=asgi.env):
    """OAuth 用户设置密码，仅允许当前未设置密码的用户调用"""
    repo = UserRepository(env.DB)
    user = await repo.get_by_id(current_user["id"])
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if user.get("password_hash"):
        raise HTTPException(status_code=409, detail="密码已设置，不可重复操作")

    password_hash = PasswordHasher.hash_password(body.password)
    await repo.update_password(current_user["id"], password_hash)
    return {"detail": "密码设置成功"}


@users_router.get("/me/login-history", response_model=LoginHistoryResponse)
async def get_my_login_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    env=asgi.env,
):
    """获取当前用户的登录历史记录，支持分页查询"""
    history_repo = LoginHistoryRepository(env.DB)
    records_raw = await history_repo.get_by_user(current_user["id"], page, page_size)
    total = await history_repo.count_by_user(current_user["id"])
    records = [
        LoginHistoryRecord(
            id=r.get("id", ""),
            action=r.get("action", ""),
            method=r.get("method"),
            ip=r.get("ip"),
            country=r.get("country"),
            city=r.get("city"),
            region=r.get("region"),
            user_agent=r.get("user_agent"),
            created_at=r.get("created_at", ""),
        )
        for r in records_raw
    ]
    return LoginHistoryResponse(records=records, total=total, page=page, page_size=page_size)
