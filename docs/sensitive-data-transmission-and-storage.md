# 敏感信息传输与存储方案

## 概述

本文档系统梳理 Cloudflare Auth 项目中所有敏感信息的传输方案与存储方案，涵盖密码、JWT 令牌、OAuth 凭据、API 密钥、邮箱验证码等关键数据的全生命周期安全策略。

项目运行在 Cloudflare Workers Python（Pyodide）环境中，使用 D1 作为关系型数据库、KV 作为键值存储，所有外部通信均通过 HTTPS 加密传输。

---

## 1. 密码

### 1.1 传输方案

| 阶段 | 协议 | 说明 |
|------|------|------|
| 客户端 → Workers | HTTPS（TLS 1.3） | 密码以 JSON 明文字段通过 HTTPS POST 请求体传输，TLS 层保证传输加密 |
| Workers 内部 | 内存操作 | 密码在内存中完成哈希计算后立即丢弃，不写入日志或临时存储 |

### 1.2 存储方案

- **算法**：PBKDF2-HMAC-SHA256
- **迭代次数**：100,000 次
- **盐值**：每个密码独立生成 16 字节（128 位）随机盐值（`os.urandom(16)`）
- **存储格式**：`{salt_hex}${hash_hex}`，存入 D1 数据库 `users.password_hash` 字段
- **验证流程**：从存储值中分离盐值，使用相同参数重新计算哈希，通过恒定时间比较（`==` 对 hex 字符串）验证一致性

### 1.3 设计决策

由于 Pyodide 环境不支持 `bcrypt` 原生库，采用 Python 标准库内置的 `hashlib.pbkdf2_hmac` 实现。该方案符合 NIST SP 800-132 推荐的密码哈希标准。

---

## 2. JWT 令牌

### 2.1 传输方案

| 场景 | 方式 | 说明 |
|------|------|------|
| 登录响应 | HTTPS 响应体 JSON | `access_token` 和 `refresh_token` 通过 API 响应体返回 |
| API 请求认证 | HTTP Header | `Authorization: Bearer {access_token}`，通过 HTTPS 传输 |
| OAuth 回调 | 一次性授权码 | 令牌不再通过 URL 参数传递（详见第 3 节） |
| 客户端存储 | localStorage | 前端将令牌存储在浏览器 localStorage 中 |

### 2.2 签名与验证

- **算法**：HMAC-SHA256（HS256）
- **实现**：使用 Python 标准库 `hmac` + `hashlib` + `base64` 手动实现，因 Pyodide 环境不支持 `PyJWT` 库
- **签名密钥**：`JWT_SECRET`，通过 Cloudflare Secrets 管理（详见第 6 节）
- **签名验证**：使用 `hmac.compare_digest()` 进行恒定时间比较，防止时序攻击

### 2.3 令牌结构

```json
{
  "sub": "user_id",
  "username": "用户名",
  "role": "user",
  "type": "access | refresh",
  "jti": "UUID v4 唯一标识",
  "iat": 1234567890,
  "exp": 1234567890
}
```

### 2.4 有效期策略

| 令牌类型 | 有效期 | 说明 |
|----------|--------|------|
| access_token（密码登录） | 15 分钟 | 短期令牌，用于 API 认证 |
| access_token（OAuth 登录） | 与 Google 返回的 `expires_in` 一致（通常 1 小时） | 与第三方令牌生命周期对齐 |
| refresh_token | 7 天 | 长期令牌，用于刷新 access_token |

### 2.5 令牌黑名单（注销机制）

- **存储位置**：Cloudflare KV
- **Key 格式**：`blacklist:{jti}`（使用令牌的 `jti` claim 作为标识）
- **Value**：`"1"`
- **TTL**：与令牌剩余有效期一致，过期后 KV 自动清理
- **验证流程**：每次 API 请求时，认证中间件在验证签名和有效期后，额外检查 KV 黑名单

---

## 3. OAuth 令牌传递（一次性授权码机制）

### 3.1 问题背景

OAuth 2.0 授权码流程中，后端完成令牌交换后需将系统 JWT 传递给前端。早期方案通过 URL 查询参数传递令牌：

```
/oauth-callback.html?access_token=eyJ...&refresh_token=eyJ...
```

该方案存在以下安全风险：

| 风险 | 说明 |
|------|------|
| 浏览器历史记录 | 令牌明文记录在浏览器地址栏历史中 |
| 服务器访问日志 | URL 参数可能被 CDN、代理服务器或 Web 服务器记录 |
| HTTP Referer 头 | 用户从回调页面导航到外部链接时，Referer 头会携带完整 URL |
| 肩窥攻击 | 令牌在地址栏中可见 |

### 3.2 当前方案：一次性短期授权码

```
浏览器 ──GET /auth/oauth/callback/google──→ Workers 后端
                                              │
                                              ├─ 生成 JWT tokens
                                              ├─ 生成随机授权码 (secrets.token_urlsafe(32))
                                              ├─ 将 tokens 存入 KV: oauth_exchange:{code}  TTL=60s
                                              │
浏览器 ←──302 /oauth-callback.html?code=xxx──┘
  │
  ├─ 前端提取 URL 中的 code（不含任何令牌）
  │
  ├──POST /auth/oauth/exchange {code: "xxx"}──→ Workers 后端
  │                                               │
  │                                               ├─ 从 KV 读取 oauth_exchange:{code}
  │                                               ├─ 立即删除该 KV 条目（一次性使用）
  │                                               │
  │ ←──200 {access_token, refresh_token}─────────┘
  │
  └─ 存入 localStorage，跳转主页
```

### 3.3 安全特性

| 特性 | 实现 |
|------|------|
| 令牌不暴露在 URL 中 | URL 仅携带不透明的随机授权码，令牌通过 HTTPS POST 响应体返回 |
| 一次性使用 | 授权码在首次交换后立即从 KV 中删除，无法重放 |
| 短期有效 | 授权码 TTL 为 60 秒，超时自动失效 |
| 密码学安全随机 | 使用 `secrets.token_urlsafe(32)` 生成 256 位随机码，不可预测 |
| 传输加密 | 令牌交换通过 HTTPS POST 请求完成 |

### 3.4 KV 存储结构

| Key | Value | TTL |
|-----|-------|-----|
| `oauth_exchange:{code}` | `{"access_token": "...", "refresh_token": "..."}` | 60 秒 |

---

## 4. OAuth State 参数（CSRF 防护）

### 4.1 传输方案

- 后端生成随机 `state` 值，附加到 OAuth 授权 URL 中
- OAuth Provider 回调时原样返回 `state` 参数
- 后端验证 `state` 与 KV 中存储的值一致后立即删除

### 4.2 存储方案

| Key | Value | TTL |
|-----|-------|-----|
| `oauth_state:{state_value}` | `{"provider": "google", "created_at": timestamp}` | 300 秒 |

### 4.3 安全特性

- 防止 CSRF 攻击：攻击者无法伪造有效的 `state` 参数
- 一次性使用：验证后立即从 KV 中删除
- 短期有效：5 分钟 TTL 防止过期 state 被重放

---

## 5. 邮箱验证码

### 5.1 传输方案

| 阶段 | 方式 | 说明 |
|------|------|------|
| 生成 | `random.SystemRandom().randint(100000, 999999)` | 使用系统级安全随机源 |
| 发送 | Resend REST API（HTTPS） | 验证码嵌入 HTML 邮件模板，通过 HTTPS 调用 Resend API 发送 |
| 提交 | HTTPS POST 请求体 | 用户在注册表单中提交验证码 |

### 5.2 存储方案

| Key | Value | TTL | 说明 |
|-----|-------|-----|------|
| `email_code:{email}` | 6 位数字字符串 | 300 秒 | 验证码本体 |
| `email_cooldown:{email}` | `"1"` | 60 秒 | 防重复发送冷却标记 |

### 5.3 安全特性

- **有效期限制**：验证码 5 分钟后自动过期（KV TTL）
- **防重复发送**：冷却期内拒绝重复请求（HTTP 429）
- **一次性使用**：注册成功后立即从 KV 中删除验证码
- **人机验证前置**：发送验证码前必须通过 Cloudflare Turnstile 人机验证
- **邮箱预校验**：发送前检查邮箱是否已注册，防止信息泄露
- **冷却标记时序**：仅在邮件发送成功后才设置冷却标记，避免发送失败时锁定用户

---

## 6. 密钥与 API Key 管理

### 6.1 Cloudflare Secrets（生产环境）

以下敏感配置通过 `wrangler secret put` 命令设置为 Cloudflare Secrets，运行时通过 `env.{SECRET_NAME}` 访问，不存储在代码仓库或配置文件中：

| Secret 名称 | 用途 | 设置命令 |
|-------------|------|---------|
| `JWT_SECRET` | JWT 签名密钥 | `npx wrangler secret put JWT_SECRET` |
| `GOOGLE_CLIENT_SECRET` | Google OAuth 2.0 客户端密钥 | `npx wrangler secret put GOOGLE_CLIENT_SECRET` |
| `RESEND_API_KEY` | Resend 邮件发送 API 密钥 | `npx wrangler secret put RESEND_API_KEY` |
| `TURNSTILE_SECRET_KEY` | Cloudflare Turnstile 验证密钥 | `npx wrangler secret put TURNSTILE_SECRET_KEY` |

### 6.2 环境变量（非敏感公开配置）

以下配置通过 `wrangler.jsonc` 的 `vars` 字段管理，为非敏感的公开配置：

| 变量名 | 用途 |
|--------|------|
| `GOOGLE_CLIENT_ID` | Google OAuth 客户端 ID（公开） |
| `OAUTH_REDIRECT_BASE_URL` | OAuth 回调基础 URL |
| `TURNSTILE_SITE_KEY` | Turnstile 前端 Site Key（公开） |
| `RESEND_FROM_EMAIL` | 发件人邮箱地址 |

### 6.3 本地开发环境

- 本地开发使用 `.dev.vars` 文件存储 Secrets，该文件已加入 `.gitignore`
- 提供 `.dev.vars.example` 模板文件，包含占位符值，供开发者参考

---

## 7. 数据库敏感字段

### 7.1 D1 数据库

| 表 | 敏感字段 | 存储方式 | API 响应中是否暴露 |
|----|---------|---------|-------------------|
| `users` | `password_hash` | PBKDF2-SHA256 哈希值 | 否，所有 API 响应均排除该字段 |
| `oauth_accounts` | `provider_user_id` | 明文（第三方平台用户标识） | 仅在 `/users/me/detail` 中返回给当前用户 |
| `oauth_accounts` | `access_token_expires_at` | 明文时间戳 | 否 |
| `login_history` | `ip` | 明文 IP 地址 | 仅在 `/users/me/login-history` 中返回给当前用户 |

### 7.2 API 响应过滤

- `GET /users/me`：返回 `id`、`username`、`email`、`role`、`created_at`，不包含 `password_hash`
- `GET /users/me/detail`：额外返回 `has_password`（布尔值）和 `oauth_accounts` 列表，不包含 `password_hash` 原始值
- 登录失败时统一返回"凭据无效"，不区分"邮箱不存在"和"密码错误"，防止用户枚举攻击

---

## 8. 前端安全策略

### 8.1 令牌存储

- **存储位置**：浏览器 `localStorage`
- **清理时机**：用户主动退出、令牌过期（API 返回 401）、OAuth 回调失败
- **风险说明**：`localStorage` 可被同源 JavaScript 访问，需防范 XSS 攻击

### 8.2 MVVM 架构分离

所有页面遵循 MVVM 架构，JavaScript 逻辑从 HTML 中完全分离到独立 `.js` 文件：

| 页面 | ViewModel 文件 |
|------|---------------|
| 登录页 | `public/scripts/login.js` |
| 注册页 | `public/scripts/register.js` |
| 主页 | `public/scripts/index.js` |
| 个人信息页 | `public/scripts/profile.js` |
| OAuth 回调页 | `public/scripts/oauth-callback.js` |

分离内联脚本减少了 XSS 攻击面，并为后续引入 Content Security Policy（CSP）`script-src` 策略奠定基础。

### 8.3 认证检查

- 所有受保护页面在加载时同步检查 `localStorage` 中的 `access_token`
- 未持有令牌时立即重定向到登录页，阻止页面内容渲染
- API 返回 401 时自动清除令牌并重定向，防止使用失效令牌

---

## 9. 安全总结

| 敏感数据 | 传输加密 | 存储方式 | 生命周期管理 |
|----------|---------|---------|-------------|
| 用户密码 | HTTPS | PBKDF2-SHA256 哈希 + 随机盐值 | 仅存储哈希，原文不保留 |
| JWT 令牌 | HTTPS（Header / 响应体） | 客户端 localStorage | 短期有效 + KV 黑名单注销 |
| OAuth 交换码 | HTTPS（URL 参数，不含令牌） | KV（TTL=60s） | 一次性使用后立即删除 |
| OAuth State | HTTPS（URL 参数） | KV（TTL=300s） | 一次性使用后立即删除 |
| 邮箱验证码 | HTTPS + 邮件（TLS） | KV（TTL=300s） | 使用后立即删除 |
| JWT 签名密钥 | Cloudflare 内部 | Cloudflare Secrets | 运行时注入，不入库 |
| OAuth Client Secret | Cloudflare 内部 | Cloudflare Secrets | 运行时注入，不入库 |
| Resend API Key | HTTPS（Bearer Token） | Cloudflare Secrets | 运行时注入，不入库 |
| Turnstile Secret Key | HTTPS（POST Body） | Cloudflare Secrets | 运行时注入，不入库 |
