# Cloudflare Auth

基于 Cloudflare Workers Python 运行时的用户认证与授权系统，使用 FastAPI 框架构建，支持密码登录与 Google OAuth 2.0 第三方登录。

## 技术栈

- **运行时**：Cloudflare Workers（Python / Pyodide）
- **Web 框架**：FastAPI
- **数据库**：Cloudflare D1（SQLite）
- **KV 存储**：Cloudflare Workers KV（令牌黑名单 & OAuth State）
- **认证**：JWT（HS256，手动实现）+ PBKDF2-SHA256 密码哈希
- **第三方登录**：Google OAuth 2.0 授权码流程
- **前端**：静态 HTML + TailwindCSS CDN + Vanilla JavaScript

## 项目结构

```
src/
├── main.py                  # FastAPI 应用入口，路由注册
├── schema.sql               # D1 数据库建表 DDL
├── auth/
│   ├── router.py            # 认证路由（注册/登录/刷新/注销）
│   ├── oauth_router.py      # OAuth 路由（授权/回调）
│   ├── service.py           # 认证业务逻辑
│   ├── oauth_service.py     # OAuth 业务逻辑
│   ├── dependencies.py      # FastAPI 依赖注入（当前用户、角色校验）
│   └── models.py            # Pydantic 请求/响应模型
├── users/
│   ├── router.py            # 用户路由（个人信息/地理位置/登录历史）
│   ├── repository.py        # 用户 & OAuth 账号数据库操作
│   └── login_history_repository.py  # 登录历史数据库操作
└── core/
    ├── jwt_utils.py         # JWT 生成、验证与黑名单管理
    ├── password.py          # PBKDF2-SHA256 密码哈希
    └── config.py            # 配置常量（含 OAuth 端点）
public/
├── index.html               # 用户主页
├── login.html               # 登录页
├── register.html            # 注册页
├── profile.html             # 个人信息页
├── oauth-callback.html      # OAuth 回调中转页
├── styles/common.css        # 公共样式
└── scripts/alert.js         # Alert 组件
migrations/                  # D1 数据库迁移脚本
scripts/deploy.bat           # 自动化部署脚本
```

## API 端点

| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| POST | `/auth/register` | 用户注册 | 否 |
| POST | `/auth/login` | 密码登录 | 否 |
| POST | `/auth/refresh` | 刷新令牌 | 否 |
| POST | `/auth/logout` | 注销登录 | 是 |
| GET | `/auth/oauth/{provider}` | 发起 OAuth 登录 | 否 |
| GET | `/auth/oauth/callback/{provider}` | OAuth 回调处理 | 否 |
| GET | `/users/me` | 获取当前用户信息 | 是 |
| GET | `/users/me/detail` | 获取用户详细信息 | 是 |
| GET | `/users/me/geo` | 获取 IP 与地理位置 | 是 |
| GET | `/users/me/login-history` | 登录历史（分页） | 是 |
| PUT | `/users/me/password` | OAuth 用户设置密码 | 是 |

## 快速开始

### 前置条件

- [Node.js](https://nodejs.org/) ≥ 18
- [uv](https://docs.astral.sh/uv/)（Python 包管理器）
- Cloudflare 账号

### 本地开发

1. 克隆仓库并安装依赖：

```bash
git clone <repository-url>
cd cloudflare-auth
npm install
```

2. 复制环境变量模板并填入实际值：

```bash
cp .dev.vars.example .dev.vars
```

`.dev.vars` 中需要配置：

- `JWT_SECRET` — JWT 签名密钥（建议使用 `openssl rand -hex 32` 生成）
- `GOOGLE_CLIENT_SECRET` — Google OAuth 2.0 客户端密钥

3. 在 `wrangler.jsonc` 中配置 D1 数据库和 KV 命名空间的绑定 ID，以及 Google OAuth 客户端 ID。

4. 启动本地开发服务器：

```bash
npm run dev
```

### 数据库初始化

使用 Wrangler 执行迁移脚本初始化 D1 数据库：

```bash
# 本地开发数据库
npx wrangler d1 execute cloudflare-auth-db --local --file=migrations/0001_init.sql
npx wrangler d1 execute cloudflare-auth-db --local --file=migrations/0002_oauth_accounts_extend.sql
npx wrangler d1 execute cloudflare-auth-db --local --file=migrations/0003_login_history.sql

# 远程生产数据库
npx wrangler d1 execute cloudflare-auth-db --remote --file=migrations/0001_init.sql
npx wrangler d1 execute cloudflare-auth-db --remote --file=migrations/0002_oauth_accounts_extend.sql
npx wrangler d1 execute cloudflare-auth-db --remote --file=migrations/0003_login_history.sql
```

### 部署

配置 Cloudflare Secrets：

```bash
npx wrangler secret put JWT_SECRET
npx wrangler secret put GOOGLE_CLIENT_SECRET
```

部署到 Cloudflare Workers：

```bash
npx wrangler deploy
```

或使用自动化部署脚本（包含配置还原与脱敏）：

```bash
scripts\deploy.bat
```

## 设计要点

- **JWT 手动实现**：Pyodide 环境不支持 PyJWT，使用 `hashlib` + `hmac` + `base64` 实现 HS256 签名验证。
- **PBKDF2 密码哈希**：Pyodide 不支持 bcrypt，采用 `hashlib.pbkdf2_hmac`（SHA-256）配合随机盐值。
- **令牌黑名单**：基于 KV 存储，利用 TTL 自动清理过期条目。
- **OAuth State 防护**：使用 KV 存储 OAuth state 参数，设置 5 分钟 TTL 防止 CSRF 攻击。
- **D1 空值处理**：Pyodide 中 Python `None` 转为 JS `undefined`，D1 会拒绝该值，通过辅助函数统一转换为空字符串。

## 许可证

私有项目，未公开授权。
