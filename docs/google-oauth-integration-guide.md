# Cloudflare Workers (Python) 集成 Google OAuth 2.0 第三方登录完整指南

## 目录

1. [技术背景与架构概述](#1-技术背景与架构概述)
2. [前置准备](#2-前置准备)
3. [OAuth 2.0 授权码流程详解](#3-oauth-20-授权码流程详解)
4. [Google Cloud Console 配置](#4-google-cloud-console-配置)
5. [后端实现](#5-后端实现)
6. [前端实现](#6-前端实现)
7. [密钥安全管理](#7-密钥安全管理)
8. [遇到的问题与解决方案](#8-遇到的问题与解决方案)
9. [注意事项与最佳实践](#9-注意事项与最佳实践)
10. [完整请求流程示例](#10-完整请求流程示例)

---

## 1. 技术背景与架构概述

### 技术栈

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| 运行时 | Cloudflare Workers (Python) | 基于 Pyodide 的 Python WASM 运行时 |
| Web 框架 | FastAPI | 通过 ASGI 适配层运行在 Workers 上 |
| 数据库 | Cloudflare D1 (SQLite) | 存储用户数据和 OAuth 账号关联 |
| 键值存储 | Cloudflare KV | 存储 OAuth state 参数和令牌黑名单 |
| HTTP 客户端 | Pyodide `js.fetch` | Workers 环境内置的 Fetch API |
| JWT | 手动实现 (hmac + hashlib) | Pyodide 不支持 PyJWT 库 |

### 架构流程

```
浏览器                    Workers 后端                Google OAuth
  │                           │                          │
  │  GET /auth/oauth/google   │                          │
  │ ─────────────────────────>│                          │
  │                           │  生成 state, 存入 KV     │
  │  302 重定向到 Google       │                          │
  │ <─────────────────────────│                          │
  │                           │                          │
  │  用户在 Google 页面授权    │                          │
  │ ──────────────────────────────────────────────────── >│
  │                           │                          │
  │  302 回调 ?code=xxx&state=yyy                        │
  │ <────────────────────────────────────────────────────│
  │                           │                          │
  │  GET /auth/oauth/callback/google?code=xxx&state=yyy  │
  │ ─────────────────────────>│                          │
  │                           │  验证 state (KV)         │
  │                           │  POST 交换 code→token    │
  │                           │ ────────────────────────>│
  │                           │  {access_token}          │
  │                           │ <────────────────────────│
  │                           │  GET /userinfo           │
  │                           │ ────────────────────────>│
  │                           │  {email, name, id}       │
  │                           │ <────────────────────────│
  │                           │  查找/创建用户 (D1)      │
  │                           │  生成 JWT tokens         │
  │  302 → /oauth-callback.html?tokens                   │
  │ <─────────────────────────│                          │
  │  存储 tokens, 跳转首页    │                          │
```

---

## 2. 前置准备

### 2.1 Google Cloud 项目配置

1. 访问 [Google Cloud Console](https://console.cloud.google.com/)
2. 创建或选择一个项目
3. 启用 **Google+ API** 或 **People API**（用于获取用户信息）
4. 在 **APIs & Services → Credentials** 中创建 OAuth 2.0 客户端 ID

### 2.2 所需凭据

| 凭据 | 类型 | 存储位置 |
|------|------|---------|
| `GOOGLE_CLIENT_ID` | 公开标识符 | `wrangler.jsonc` 的 `vars` |
| `GOOGLE_CLIENT_SECRET` | 敏感密钥 | Cloudflare Secrets / `.dev.vars` |

### 2.3 Google OAuth 端点

```python
# src/core/config.py
OAUTH_PROVIDERS = {
    "google": {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v2/userinfo",
        "scope": "openid email profile",
    },
}
```

- **authorize_url**: 用户授权页面，浏览器重定向到此地址
- **token_url**: 后端使用授权码 (code) 交换 access_token 的端点
- **userinfo_url**: 使用 access_token 获取用户邮箱和姓名的端点
- **scope**: 请求的权限范围，`openid email profile` 获取基本身份信息

---

## 3. OAuth 2.0 授权码流程详解

Google OAuth 使用标准的 **Authorization Code Flow**（授权码流程），这是服务端应用推荐的 OAuth 流程。

### 3.1 流程步骤

**Step 1 — 发起授权请求**

后端生成授权 URL，将用户重定向到 Google 授权页面：

```
https://accounts.google.com/o/oauth2/v2/auth?
  client_id=YOUR_CLIENT_ID&
  redirect_uri=https://your-domain/auth/oauth/callback/google&
  response_type=code&
  scope=openid+email+profile&
  state=RANDOM_STATE_VALUE
```

关键参数：
- `client_id`: Google Cloud Console 中创建的客户端 ID
- `redirect_uri`: 授权完成后 Google 回调的地址，必须与 Console 中配置的完全一致
- `response_type=code`: 指定使用授权码流程
- `scope`: 请求的权限范围
- `state`: 随机生成的防 CSRF 令牌，存储在 KV 中用于回调时验证

**Step 2 — 用户授权**

用户在 Google 页面登录并同意授权。Google 将用户重定向回 `redirect_uri`，URL 中携带 `code` 和 `state` 参数。

**Step 3 — 授权码交换 access_token**

后端使用 `code` 向 Google token 端点发送 POST 请求，交换 access_token：

```
POST https://oauth2.googleapis.com/token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code&
code=AUTHORIZATION_CODE&
redirect_uri=https://your-domain/auth/oauth/callback/google&
client_id=YOUR_CLIENT_ID&
client_secret=YOUR_CLIENT_SECRET
```

**Step 4 — 获取用户信息**

使用 access_token 调用 Google userinfo API：

```
GET https://www.googleapis.com/oauth2/v2/userinfo
Authorization: Bearer ACCESS_TOKEN
```

返回：
```json
{
  "id": "google_user_id",
  "email": "user@gmail.com",
  "name": "用户名",
  "picture": "https://..."
}
```

**Step 5 — 创建/关联本地用户**

根据 Google 返回的 email 和 id，在本地数据库中查找或创建用户，生成系统内部的 JWT token。

---

## 4. Google Cloud Console 配置

### 4.1 创建 OAuth 2.0 客户端

1. 进入 [Google Cloud Console → Credentials](https://console.cloud.google.com/apis/credentials)
2. 点击 **Create Credentials → OAuth client ID**
3. 应用类型选择 **Web application**
4. 填写名称（如 `cloudflare-auth`）

### 4.2 配置授权重定向 URI

在 **Authorized redirect URIs** 中添加：

```
https://your-domain.workers.dev/auth/oauth/callback/google
```

如果使用自定义域名：
```
https://auth.yourdomain.com/auth/oauth/callback/google
```

> **重要**: redirect_uri 必须与代码中构建的回调地址完全一致（包括协议、域名、路径），否则 Google 会返回 `redirect_uri_mismatch` 错误。

### 4.3 配置 OAuth 同意屏幕

1. 进入 **OAuth consent screen**
2. 选择 **External**（面向所有 Google 用户）
3. 填写应用名称、用户支持邮箱、开发者联系信息
4. 添加 Scope: `openid`, `email`, `profile`
5. 如果应用处于测试阶段，需要在 **Test users** 中添加测试用户邮箱

> **注意**: 处于"Testing"状态的应用只有添加到测试用户列表中的 Google 账号才能完成授权。发布到"Production"需要通过 Google 审核。

---

## 5. 后端实现

### 5.1 数据库表结构

OAuth 登录需要额外的 `oauth_accounts` 表来存储第三方账号关联：

```sql
-- users 表：password_hash 设为可空，OAuth 注册的用户没有密码
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT,          -- 可空，OAuth 用户无密码
    role TEXT NOT NULL DEFAULT 'user',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- oauth_accounts 表：存储用户与第三方账号的关联关系
CREATE TABLE IF NOT EXISTS oauth_accounts (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    provider TEXT NOT NULL,              -- 'google'
    provider_user_id TEXT NOT NULL,      -- Google 返回的用户 ID
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(provider, provider_user_id)   -- 同一提供商的同一用户只能关联一次
);
```

设计要点：
- `users.password_hash` 为可空字段，因为通过 OAuth 注册的用户不设置密码
- `oauth_accounts` 通过 `UNIQUE(provider, provider_user_id)` 约束防止重复关联
- 一个 `user` 可以关联多个 OAuth 账号，通过 `user_id` 外键关联

### 5.2 OAuth 路由层 (`src/auth/oauth_router.py`)

路由层负责处理 HTTP 请求，构建 `OAuthService` 实例并调用业务逻辑：

```python
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from urllib.parse import urlencode
import asgi

oauth_router = APIRouter(prefix="/auth/oauth", tags=["oauth"])

def _build_oauth_service(env) -> OAuthService:
    """通过 Cloudflare env 绑定构建 OAuthService 实例"""
    repo = UserRepository(env.DB)          # D1 数据库绑定
    return OAuthService(
        repo,
        env.TOKEN_BLACKLIST,               # KV 绑定
        env.JWT_SECRET,                    # Secret 绑定
        env                                # 完整 env（用于读取 CLIENT_ID 等）
    )

@oauth_router.get("/{provider}")
async def oauth_authorize(provider: str, request: Request, env=asgi.env):
    """Step 1: 生成授权 URL 并重定向用户到 Google"""
    service = _build_oauth_service(env)
    redirect_base = str(env.OAUTH_REDIRECT_BASE_URL).rstrip("/")
    redirect_uri = f"{redirect_base}/auth/oauth/callback/{provider}"
    authorization_url = await service.get_authorization_url(provider, redirect_uri)
    return RedirectResponse(url=authorization_url, status_code=302)

@oauth_router.get("/callback/{provider}")
async def oauth_callback(provider: str, request: Request, env=asgi.env):
    """Step 2-5: 处理 Google 回调，完成令牌交换和用户创建"""
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")

    # 用户拒绝授权
    if error:
        return RedirectResponse(url="/login.html?error=access_denied", status_code=302)

    service = _build_oauth_service(env)
    redirect_base = str(env.OAUTH_REDIRECT_BASE_URL).rstrip("/")
    redirect_uri = f"{redirect_base}/auth/oauth/callback/{provider}"

    try:
        tokens = await service.handle_callback(provider, code, state, redirect_uri)
    except HTTPException as e:
        return RedirectResponse(url=f"/login.html?error={e.detail}", status_code=302)

    # 成功：重定向到前端回调页面，携带 JWT tokens
    params = urlencode({
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
    })
    return RedirectResponse(url=f"/oauth-callback.html?{params}", status_code=302)
```

关键设计：
- 通过 `asgi.env` 依赖注入获取 Cloudflare Workers 的环境绑定（D1、KV、Secrets、Vars）
- 回调成功后通过 URL 参数将 JWT tokens 传递给前端中转页面
- 所有异常统一重定向到登录页面并携带错误信息

### 5.3 OAuth 服务层核心逻辑 (`src/auth/oauth_service.py`)

#### 生成授权 URL 并存储 state

```python
async def get_authorization_url(self, provider: str, redirect_uri: str) -> str:
    config = OAUTH_PROVIDERS[provider]

    # 生成随机 state 防止 CSRF 攻击
    state = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode("ascii")

    # 将 state 存入 KV，设置 5 分钟 TTL 自动过期
    kv_data = {"provider": provider, "created_at": int(time.time())}
    await self.kv.put(
        f"oauth_state:{state}",
        json.dumps(kv_data),
        expiration_ttl=300,  # 5 分钟
    )

    # 构建授权 URL
    params = {
        "client_id": self._get_client_id(provider),
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": config["scope"],
        "state": state,
    }
    return f"{config['authorize_url']}?{urlencode(params)}"
```

#### 使用 Pyodide `js.fetch` 交换授权码

Cloudflare Workers Python 环境基于 Pyodide，不能使用 `requests` 或 `httpx`。需要通过 `js.fetch` 调用浏览器原生 Fetch API：

```python
async def _exchange_code(self, provider: str, code: str, redirect_uri: str,
                         code_verifier: str | None = None) -> str:
    # 关键：从 Pyodide 的 js 模块导入浏览器 Fetch API
    from js import fetch, Headers

    config = OAUTH_PROVIDERS[provider]
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
        config["token_url"],
        method="POST",
        headers=headers,
        body=urlencode(body_params),
    )

    if not response.ok:
        raise HTTPException(status_code=502, detail="第三方登录服务暂时不可用")

    data = await response.json()
    return str(data.access_token)
```

#### 获取 Google 用户信息

```python
async def _get_user_info(self, provider: str, access_token: str) -> dict:
    from js import fetch, Headers

    headers = Headers.new()
    headers.set("Authorization", f"Bearer {access_token}")
    headers.set("Accept", "application/json")

    response = await fetch(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        method="GET",
        headers=headers,
    )

    data = await response.json()
    return {
        "email": str(data.email),
        "name": str(data.name or data.email.split("@")[0]),
        "provider_user_id": str(data.id),
    }
```

#### 查找或创建用户

```python
async def _find_or_create_user(self, provider, provider_user_id, email, name):
    # 1. 检查 oauth_accounts 表是否已有关联
    existing_oauth = await self.user_repo.get_oauth_account(provider, provider_user_id)
    if existing_oauth:
        return existing_oauth  # 直接返回已关联的用户

    # 2. 检查是否有相同邮箱的本地用户（可能是邮箱密码注册的）
    existing_user = await self.user_repo.get_by_email(email)
    if existing_user:
        # 将 OAuth 账号关联到已有用户
        await self.user_repo.create_oauth_account(
            existing_user["id"], provider, provider_user_id
        )
        return existing_user

    # 3. 创建全新用户（无密码）
    username = name
    # 处理用户名冲突
    if await self.user_repo.get_by_username(username):
        suffix = base64.urlsafe_b64encode(os.urandom(4)).rstrip(b"=").decode("ascii")
        username = f"{name}_{suffix}"

    user = await self.user_repo.create_user_without_password(username, email)
    await self.user_repo.create_oauth_account(user["id"], provider, provider_user_id)
    return user
```

### 5.4 读取 Secrets 的方式

在 Cloudflare Workers Python 中，Secrets 和环境变量都通过 `env` 对象访问：

```python
def _get_client_id(self, provider: str) -> str:
    """从 env.vars 读取（非敏感，配置在 wrangler.jsonc 的 vars 中）"""
    if provider == "google":
        return str(self.env.GOOGLE_CLIENT_ID)
    return ""

def _get_client_secret(self, provider: str) -> str:
    """从 env.secrets 读取（敏感，通过 wrangler secret put 设置）"""
    if provider == "google":
        return str(self.env.GOOGLE_CLIENT_SECRET)
    return ""
```

> Secrets 和 vars 在代码中的访问方式完全相同，都是 `env.KEY_NAME`。区别在于 Secrets 的值在 Dashboard 和 CLI 中不可见。

---

## 6. 前端实现

### 6.1 登录页面的 Google 登录按钮

```html
<!-- public/login.html -->
<a href="/auth/oauth/google" class="m-button-outline">
    <svg class="w-4 h-4" viewBox="0 0 24 24">
        <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92..."/>
        <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77..."/>
        <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s..."/>
        <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15..."/>
    </svg>
    Google
</a>
```

点击按钮后，浏览器直接导航到 `/auth/oauth/google`，由后端处理重定向。

### 6.2 OAuth 回调中转页面 (`public/oauth-callback.html`)

后端回调成功后，将 JWT tokens 通过 URL 参数传递到此页面：

```html
<script>
(function () {
    var params = new URLSearchParams(window.location.search);
    var accessToken = params.get('access_token');
    var refreshToken = params.get('refresh_token');
    var error = params.get('error');

    if (error) {
        showAlert(decodeURIComponent(error), 'error', 0);
        setTimeout(function () {
            window.location.replace('/login.html');
        }, 2000);
        return;
    }

    if (accessToken && refreshToken) {
        // 存储 tokens 到 localStorage
        localStorage.setItem('access_token', accessToken);
        localStorage.setItem('refresh_token', refreshToken);
        // 跳转到首页
        window.location.replace('/');
    } else {
        showAlert('登录参数缺失，请重新登录', 'error', 0);
        setTimeout(function () {
            window.location.replace('/login.html');
        }, 2000);
    }
})();
</script>
```

### 6.3 登录页面的 OAuth 错误处理

登录页面需要处理 OAuth 失败后的重定向错误参数：

```javascript
const urlParams = new URLSearchParams(window.location.search);
const errorParam = urlParams.get('error');
if (errorParam) {
    const errorMessages = {
        'access_denied': '您已取消第三方登录授权',
        'oauth_failed': '第三方登录失败，请稍后重试',
        'invalid_state': '授权请求无效或已过期，请重新登录'
    };
    showAlert(errorMessages[errorParam] || '登录出错，请重试', 'error');
}
```

---

## 7. 密钥安全管理

### 7.1 生产环境：Cloudflare Secrets

使用 `wrangler secret put` 将敏感值加密存储到 Cloudflare：

```bash
# 设置 Google OAuth client secret
npx wrangler secret put GOOGLE_CLIENT_SECRET
# 交互式输入从 Google Cloud Console 获取的 client_secret 值

# 设置 JWT 签名密钥
npx wrangler secret put JWT_SECRET
# 输入一个强随机字符串，如: openssl rand -hex 32 的输出
```

### 7.2 本地开发：`.dev.vars` 文件

本地开发时，Secrets 通过 `.dev.vars` 文件提供（已被 `.gitignore` 忽略）：

```bash
# .dev.vars
JWT_SECRET="local-dev-jwt-secret-change-me"
GOOGLE_CLIENT_SECRET="your-google-client-secret"
```

### 7.3 wrangler.jsonc 中声明必需 Secrets

```jsonc
// wrangler.jsonc
{
    "secrets": {
        "required": ["JWT_SECRET", "GOOGLE_CLIENT_SECRET"]
    },
    "vars": {
        "GOOGLE_CLIENT_ID": "your-client-id.apps.googleusercontent.com",
        "OAUTH_REDIRECT_BASE_URL": "https://your-domain.workers.dev"
    }
}
```

`secrets.required` 的作用：
- `wrangler deploy` 时验证所有必需 Secrets 已设置，未设置则部署失败
- `wrangler types` 时生成正确的类型定义
- 不存储实际值，仅声明名称

### 7.4 安全原则

| 做法 | 说明 |
|------|------|
| ✅ `client_id` 放在 `vars` | 公开标识符，不敏感 |
| ✅ `client_secret` 放在 Secrets | 敏感密钥，加密存储 |
| ✅ `.dev.vars` 被 `.gitignore` | 本地密钥不进入版本控制 |
| ✅ 提供 `.dev.vars.example` | 团队成员知道需要哪些密钥 |
| ❌ 不要在 `vars` 中放 secret | `vars` 的值在 Dashboard 中可见 |
| ❌ 不要硬编码在源代码中 | 代码提交到 Git 后密钥泄露 |

---

## 8. 遇到的问题与解决方案

### 问题 1：Pyodide 环境不支持标准 HTTP 客户端库

**现象**: `import requests` 或 `import httpx` 在 Cloudflare Workers Python 环境中抛出 `ModuleNotFoundError`。

**原因**: Cloudflare Workers Python 运行时基于 Pyodide（Python 编译为 WebAssembly），不支持底层 socket 操作，因此 `requests`、`httpx`、`urllib3` 等依赖 socket 的库无法使用。

**解决方案**: 使用 Pyodide 内置的 `js.fetch` 调用浏览器原生 Fetch API：

```python
from js import fetch, Headers

headers = Headers.new()
headers.set("Content-Type", "application/x-www-form-urlencoded")

response = await fetch(url, method="POST", headers=headers, body=encoded_body)
data = await response.json()
# 注意：data 是 JavaScript 对象，通过属性访问（data.access_token）而非字典访问
```

**注意**: `js.fetch` 返回的 JSON 数据是 JavaScript 对象（JsProxy），需要通过属性访问（`data.access_token`）而非 Python 字典语法（`data["access_token"]`）。

### 问题 2：Pyodide 不支持 PyJWT 库

**现象**: `import jwt` 失败，无法使用 PyJWT 进行 JWT 编码/解码。

**原因**: PyJWT 依赖 C 扩展（`cryptography` 库），Pyodide 环境中不可用。

**解决方案**: 使用 Python 标准库手动实现 JWT HS256：

```python
import hmac, hashlib, base64, json, time

def create_token(payload: dict, secret: str, expires_minutes: int) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload["exp"] = int(time.time()) + expires_minutes * 60
    payload["iat"] = int(time.time())

    # Base64url 编码
    h = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=")
    p = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=")
    signing_input = h + b"." + p

    # HMAC-SHA256 签名
    sig = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    s = base64.urlsafe_b64encode(sig).rstrip(b"=")

    return (signing_input + b"." + s).decode()
```

### 问题 3：OAuth state 参数的 CSRF 防护

**现象**: 如果不验证 state 参数，攻击者可以构造恶意回调 URL 进行 CSRF 攻击。

**解决方案**: 使用 Cloudflare KV 存储 state，设置 TTL 自动过期：

```python
# 生成 state 时存入 KV
state = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode("ascii")
await kv.put(f"oauth_state:{state}", json.dumps(kv_data), expiration_ttl=300)

# 回调时验证并删除 state（一次性使用）
state_data_raw = await kv.get(f"oauth_state:{state}")
if state_data_raw is None:
    raise HTTPException(status_code=400, detail="授权请求无效或已过期")
await kv.delete(f"oauth_state:{state}")  # 防止重放攻击
```

关键点：
- state 使用 `os.urandom(32)` 生成 256 位随机值，不可预测
- KV TTL 设为 300 秒（5 分钟），超时自动清理
- 验证后立即删除，确保 state 只能使用一次

### 问题 4：`redirect_uri_mismatch` 错误

**现象**: Google 回调时返回 `Error 400: redirect_uri_mismatch`。

**原因**: 代码中构建的 `redirect_uri` 与 Google Cloud Console 中配置的不一致。

**解决方案**:
1. 确保 `OAUTH_REDIRECT_BASE_URL` 环境变量与实际部署域名一致
2. 在 Google Cloud Console 的 **Authorized redirect URIs** 中添加完整路径
3. 注意协议（`https`）、域名、端口、路径必须完全匹配

```
# 正确示例
https://auth.yourdomain.com/auth/oauth/callback/google

# 常见错误
http://auth.yourdomain.com/auth/oauth/callback/google   ← 协议错误（http vs https）
https://auth.yourdomain.com/auth/oauth/callback/google/  ← 多余的尾部斜杠
https://auth.yourdomain.com/auth/oauth/callback           ← 路径不完整
```

### 问题 5：OAuth 用户与本地用户的账号合并

**现象**: 用户先用邮箱密码注册，后用相同邮箱的 Google 账号登录，期望关联到同一账户。

**解决方案**: 在 `_find_or_create_user` 中实现三级查找策略：

1. 先查 `oauth_accounts` 表（provider + provider_user_id）→ 已关联则直接返回
2. 再查 `users` 表（email）→ 邮箱匹配则创建关联记录
3. 都不存在则创建新用户（无密码）+ 关联记录

### 问题 6：KV `get()` 返回值类型处理

**现象**: Cloudflare KV 的 `get()` 在 Python 中返回的可能是 `JsProxy` 对象而非 Python 字符串。

**解决方案**: 显式转换为 Python 字符串后再解析 JSON：

```python
state_data_raw = await self.kv.get(f"oauth_state:{state}")
if state_data_raw is None or not state_data_raw:
    raise HTTPException(status_code=400, detail="授权请求无效或已过期")

# 关键：显式转换为 Python str
state_data_str = str(state_data_raw)
state_data = json.loads(state_data_str)
```

### 问题 7：用户名冲突处理

**现象**: Google 返回的用户名（`name` 字段）可能与数据库中已有用户名冲突，导致 `UNIQUE constraint` 错误。

**解决方案**: 检测冲突后追加随机后缀：

```python
username = name
existing_name = await self.user_repo.get_by_username(username)
if existing_name:
    suffix = base64.urlsafe_b64encode(os.urandom(4)).rstrip(b"=").decode("ascii")
    username = f"{name}_{suffix}"
```

---

## 9. 注意事项与最佳实践

### 9.1 安全相关

1. **永远不要在前端暴露 `client_secret`** — client_secret 只在后端使用，前端只需要 client_id
2. **state 参数必须验证** — 防止 CSRF 攻击，使用后立即删除
3. **统一错误信息** — OAuth 失败时不暴露内部细节，统一重定向到登录页面
4. **tokens 通过 URL 参数传递的风险** — 当前实现将 JWT 通过 URL 参数传递给前端回调页面，tokens 会出现在浏览器历史记录和服务器日志中。生产环境可考虑使用 `httpOnly` Cookie 或一次性授权码替代

### 9.2 Google OAuth 特定注意事项

1. **测试模式限制** — OAuth 同意屏幕处于 "Testing" 状态时，只有添加到测试用户列表的 Google 账号才能授权
2. **Scope 最小化** — 只请求必要的 scope（`openid email profile`），避免请求不必要的权限
3. **Refresh Token** — Google OAuth 的 refresh_token 只在用户首次授权时返回。如需每次都获取，需要在授权 URL 中添加 `access_type=offline&prompt=consent`
4. **用户信息 API 版本** — 本项目使用 v2 API (`/oauth2/v2/userinfo`)，Google 也提供 v3 API (`/oauth2/v3/userinfo`)，返回字段略有不同

### 9.3 Cloudflare Workers 特定注意事项

1. **Pyodide 环境限制** — 不能使用 `requests`、`httpx`、`PyJWT`、`bcrypt` 等依赖 C 扩展或 socket 的库
2. **`js.fetch` 的异步特性** — 必须使用 `await` 调用，返回的 JSON 是 JavaScript 对象
3. **D1 不支持批量 SQL** — 建表语句需要逐条执行，不能一次性执行多条 SQL
4. **KV 最终一致性** — KV 写入后可能有短暂延迟才能读取到，但对 OAuth state 场景影响极小
5. **Workers CPU 时间限制** — 免费版 10ms，付费版 30s。OAuth 流程涉及多次外部 HTTP 调用，需注意总耗时

### 9.4 调试技巧

1. **本地开发** — 使用 `npx wrangler dev` 启动本地服务器，OAuth 回调需要配置 `localhost` 的 redirect_uri
2. **查看 Workers 日志** — 在 Cloudflare Dashboard → Workers → 你的 Worker → Logs 中查看实时日志
3. **Google OAuth Playground** — 使用 [OAuth 2.0 Playground](https://developers.google.com/oauthplayground/) 测试 token 交换和 userinfo API

---

## 10. 完整请求流程示例

以下是一次完整的 Google OAuth 登录的 HTTP 请求/响应流程：

```
1. 用户点击 "Google" 登录按钮
   → GET /auth/oauth/google

2. 后端生成 state，存入 KV，返回 302 重定向
   → 302 Location: https://accounts.google.com/o/oauth2/v2/auth?
       client_id=652092...&
       redirect_uri=https://auth.peliowl.asia/auth/oauth/callback/google&
       response_type=code&
       scope=openid+email+profile&
       state=abc123...

3. 用户在 Google 页面登录并授权
   → Google 302 重定向回:
     https://auth.peliowl.asia/auth/oauth/callback/google?
       code=4/0AX4XfWh...&
       state=abc123...

4. 后端处理回调
   a. 从 KV 验证 state=abc123... ✓
   b. 删除 KV 中的 state（防重放）
   c. POST https://oauth2.googleapis.com/token
      → 获取 Google access_token
   d. GET https://www.googleapis.com/oauth2/v2/userinfo
      → 获取 {email: "user@gmail.com", name: "张三", id: "12345"}
   e. 查询 D1: oauth_accounts WHERE provider='google' AND provider_user_id='12345'
      → 未找到
   f. 查询 D1: users WHERE email='user@gmail.com'
      → 未找到
   g. 创建新用户: INSERT INTO users (id, username, email, role) VALUES (...)
   h. 创建关联: INSERT INTO oauth_accounts (id, user_id, provider, provider_user_id) VALUES (...)
   i. 生成 JWT access_token (15min) 和 refresh_token (7d)

5. 后端返回 302 重定向
   → 302 Location: /oauth-callback.html?
       access_token=eyJ...&
       refresh_token=eyJ...

6. 前端回调页面
   a. 从 URL 参数提取 tokens
   b. 存入 localStorage
   c. window.location.replace('/') → 跳转到首页

7. 首页加载
   a. 检查 localStorage 中的 access_token ✓
   b. GET /users/me (Authorization: Bearer eyJ...)
   c. 显示 "认证成功，欢迎 张三"
```

---

## 附录：项目文件结构

```
src/
├── main.py                  # FastAPI 入口，注册路由
├── auth/
│   ├── router.py            # 认证路由（登录、注册、刷新、注销）
│   ├── oauth_router.py      # OAuth 路由（发起授权、处理回调）
│   ├── oauth_service.py     # OAuth 业务逻辑（核心实现）
│   ├── service.py           # 认证业务逻辑
│   ├── dependencies.py      # FastAPI 依赖（JWT 验证中间件）
│   └── models.py            # Pydantic 请求/响应模型
├── users/
│   └── repository.py        # 用户数据库操作（含 OAuth 账号）
├── core/
│   ├── jwt_utils.py         # JWT 手动实现（HS256）
│   ├── password.py          # 密码哈希（PBKDF2-SHA256）
│   └── config.py            # OAuth 端点配置、常量
└── schema.sql               # D1 建表 SQL

public/
├── login.html               # 登录页面（含 Google 登录按钮）
├── register.html            # 注册页面（含 Google 登录按钮）
├── oauth-callback.html      # OAuth 回调中转页面
├── index.html               # 认证成功首页
└── profile.html             # 个人信息页

wrangler.jsonc               # Cloudflare Workers 配置（绑定、vars、secrets）
.dev.vars                    # 本地开发 secrets（gitignored）
.dev.vars.example            # secrets 模板
```
