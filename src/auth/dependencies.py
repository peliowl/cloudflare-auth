from fastapi import Depends, HTTPException, Request

import asgi
from core.jwt_utils import JWTUtil, JWTError, JWTExpiredError


async def get_current_user(request: Request, env=asgi.env) -> dict:
    """Extract Bearer token from Authorization header, decode JWT, check blacklist, return user info."""
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未提供认证令牌")

    token = auth_header[7:]
    jwt_secret = env.JWT_SECRET
    kv = env.TOKEN_BLACKLIST

    try:
        payload = JWTUtil.decode_token(token, jwt_secret)
    except JWTExpiredError:
        raise HTTPException(status_code=401, detail="令牌已过期")
    except JWTError:
        raise HTTPException(status_code=401, detail="令牌无效")

    if await JWTUtil.is_blacklisted(token, kv):
        raise HTTPException(status_code=401, detail="令牌已失效")

    return {
        "id": payload.get("sub"),
        "username": payload.get("username"),
        "role": payload.get("role"),
        "token": token,
    }


def require_role(required_role: str):
    """Factory that returns a dependency verifying the user has the required role."""
    async def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user.get("role") != required_role:
            raise HTTPException(status_code=403, detail="权限不足")
        return current_user
    return role_checker
