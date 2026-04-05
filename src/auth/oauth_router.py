from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

import asgi
from core.config import OAUTH_PROVIDERS
from auth.oauth_service import OAuthService
from users.repository import UserRepository
from users.login_history_repository import LoginHistoryRepository

oauth_router = APIRouter(prefix="/auth/oauth", tags=["oauth"])


def _build_oauth_service(env) -> OAuthService:
    repo = UserRepository(env.DB)
    return OAuthService(repo, env.TOKEN_BLACKLIST, env.JWT_SECRET, env)


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


@oauth_router.get("/{provider}")
async def oauth_authorize(provider: str, request: Request, env=asgi.env):
    """Redirect user to OAuth provider authorization page."""
    if provider not in OAUTH_PROVIDERS:
        raise HTTPException(status_code=400, detail="不支持的登录方式")

    service = _build_oauth_service(env)
    redirect_base = str(env.OAUTH_REDIRECT_BASE_URL).rstrip("/")
    redirect_uri = f"{redirect_base}/auth/oauth/callback/{provider}"

    authorization_url = await service.get_authorization_url(provider, redirect_uri)
    return RedirectResponse(url=authorization_url, status_code=302)


@oauth_router.get("/callback/{provider}")
async def oauth_callback(provider: str, request: Request, env=asgi.env):
    """Handle OAuth provider callback, exchange code for tokens."""
    if provider not in OAUTH_PROVIDERS:
        return RedirectResponse(url="/login.html?error=不支持的登录方式", status_code=302)

    code = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")

    # User denied authorization or provider returned error
    if error:
        return RedirectResponse(url=f"/login.html?error=access_denied", status_code=302)

    if not code or not state:
        return RedirectResponse(url="/login.html?error=授权请求无效", status_code=302)

    service = _build_oauth_service(env)
    redirect_base = str(env.OAUTH_REDIRECT_BASE_URL).rstrip("/")
    redirect_uri = f"{redirect_base}/auth/oauth/callback/{provider}"

    try:
        tokens = await service.handle_callback(provider, code, state, redirect_uri)
    except HTTPException as e:
        error_msg = e.detail if isinstance(e.detail, str) else "登录失败"
        return RedirectResponse(url=f"/login.html?error={error_msg}", status_code=302)
    except Exception:
        return RedirectResponse(url="/login.html?error=登录失败", status_code=302)

    # Record OAuth login history
    info = _extract_request_info(request, env)
    history_repo = LoginHistoryRepository(env.DB)
    await history_repo.create_record(
        user_id=tokens["user_id"],
        action="login",
        method=f"oauth:{provider}",
        ip=info["ip"],
        country=info["country"],
        city=info["city"],
        region=info["region"],
        user_agent=info["user_agent"],
    )

    # Redirect to OAuth callback page with tokens
    params = urlencode({
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
    })
    return RedirectResponse(url=f"/oauth-callback.html?{params}", status_code=302)
