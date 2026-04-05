# 实现计划：用户认证与授权系统

## 概述

基于设计文档，将用户认证系统拆分为增量式编码任务。每个任务构建在前一个任务之上，最终将所有组件连接起来。使用 Python + FastAPI，运行在 Cloudflare Workers 环境中。任务 1-7 覆盖核心认证功能（注册、登录、JWT、中间件），任务 8-11 覆盖 OAuth 第三方登录和前端页面，任务 12 覆盖用户主页功能。

## 任务

- [x] 1. 搭建项目结构和核心工具模块
  - [x] 1.1 创建项目目录结构和 `__init__.py` 文件
    - 创建 `src/auth/`、`src/users/`、`src/core/` 目录及其 `__init__.py`
    - 创建 `src/schema.sql` D1 建表 SQL 文件（users 表，含 id、username、email、password_hash（可空）、role、created_at 字段及索引；oauth_accounts 表，含 id、user_id、provider、provider_user_id、created_at 字段及索引和唯一约束）
    - _Requirements: 7.1, 7.3, 9.8_

  - [x] 1.2 实现密码哈希工具 `src/core/password.py`
    - 实现 `PasswordHasher` 类，包含 `hash_password(password) -> str` 和 `verify_password(password, stored_hash) -> bool`
    - 使用 `hashlib.pbkdf2_hmac("sha256", ...)` 配合 `os.urandom(16)` 生成盐值
    - 存储格式为 `salt_hex$hash_hex`
    - _Requirements: 5.1, 5.2, 5.3_

  - [ ]* 1.3 为密码哈希编写属性测试
    - **Property 6: 密码哈希验证往返一致性**
    - **Property 7: 相同密码产生不同哈希**
    - **Validates: Requirements 5.2, 5.3, 1.4**

  - [x] 1.4 实现 JWT 工具 `src/core/jwt_utils.py`
    - 实现 `JWTUtil` 类，包含 `create_token`、`decode_token`、`is_blacklisted`、`blacklist_token` 方法
    - 使用 `hmac` + `hashlib` + `base64` 手动实现 HS256 JWT 签名
    - `create_token` 接受 payload dict、secret、expires_minutes，返回 JWT 字符串
    - `decode_token` 解码并验证签名和过期时间，失败时抛出异常
    - `is_blacklisted` 和 `blacklist_token` 操作 KV 存储
    - _Requirements: 2.4, 2.5, 3.3, 3.4_

  - [ ]* 1.5 为 JWT 工具编写属性测试
    - **Property 8: 登录成功返回包含正确载荷的有效令牌**（测试 create_token + decode_token 往返）
    - **Validates: Requirements 2.1, 2.4, 2.5**

  - [x] 1.6 实现配置常量 `src/core/config.py`
    - 定义 ACCESS_TOKEN_EXPIRE_MINUTES = 15、REFRESH_TOKEN_EXPIRE_DAYS = 7 等常量
    - 定义 OAuth Provider 端点配置（Google 的授权、令牌、用户信息 URL 和 scope）
    - 定义 OAUTH_STATE_TTL = 300（秒）
    - _Requirements: 2.5, 9.1, 9.2_

- [x] 2. 实现数据层和 Pydantic 模型
  - [x] 2.1 实现 Pydantic 请求/响应模型 `src/auth/models.py`
    - 定义 RegisterRequest（username、email、password 含验证）、LoginRequest、RefreshRequest、TokenResponse、UserResponse、ErrorResponse
    - password 字段设置 min_length=8、max_length=128
    - email 使用 Pydantic EmailStr 或正则验证
    - _Requirements: 1.5, 1.6_

  - [ ]* 2.2 为输入验证编写属性测试
    - **Property 4: 短密码被拒绝**
    - **Property 5: 无效邮箱被拒绝**
    - **Validates: Requirements 1.5, 1.6**

  - [x] 2.3 实现用户仓库 `src/users/repository.py`
    - 实现 `UserRepository` 类，接受 D1 binding
    - 实现 `create_user`、`get_by_email`、`get_by_username`、`get_by_id` 方法
    - 实现 `create_user_without_password` 方法（用于 OAuth 注册，password_hash 为 None）
    - 实现 `get_oauth_account`、`create_oauth_account`、`get_oauth_accounts_by_user` 方法
    - 使用 `uuid.uuid4()` 生成用户 ID
    - D1 操作通过 `db.prepare(sql).bind(...).run()` / `.first()` 执行
    - _Requirements: 1.1, 2.1, 9.5, 9.6, 9.8_

- [x] 3. 检查点 - 确保核心工具模块正确
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 4. 实现认证服务和路由
  - [x] 4.1 实现认证服务 `src/auth/service.py`
    - 实现 `AuthService` 类，包含 `register`、`login`、`refresh_token`、`logout` 方法
    - `register`：验证邮箱/用户名唯一性 → 哈希密码 → 创建用户 → 返回用户信息
    - `login`：查询用户 → 验证密码 → 生成 access_token 和 refresh_token → 返回
    - `refresh_token`：验证 refresh_token → 检查黑名单 → 生成新令牌对
    - `logout`：将 access_token 和 refresh_token 加入 KV 黑名单（TTL 与剩余有效期一致）
    - 登录失败统一返回"凭据无效"错误信息
    - _Requirements: 1.1, 1.2, 1.3, 1.7, 2.1, 2.2, 2.3, 3.1, 3.2, 3.3_

  - [ ]* 4.2 为认证服务编写属性测试
    - **Property 1: 注册创建用户并分配默认角色**
    - **Property 2: 重复邮箱注册被拒绝**
    - **Property 3: 重复用户名注册被拒绝**
    - **Property 9: 登录失败返回统一错误信息**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.7, 2.2, 2.3**

  - [x] 4.3 实现认证依赖 `src/auth/dependencies.py`
    - 实现 `get_current_user` 依赖：从 Authorization header 提取 Bearer token → 解码 JWT → 检查黑名单 → 返回用户信息
    - 实现 `require_role(role)` 工厂函数：返回依赖函数，验证用户角色
    - 无令牌返回 401、过期返回 401、格式错误返回 401、黑名单返回 401、角色不足返回 403
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 4.4 为认证中间件编写属性测试
    - **Property 13: 中间件拒绝无效令牌**
    - **Property 14: 基于角色的访问控制**
    - **Validates: Requirements 4.2, 4.3, 4.4, 4.5**

  - [x] 4.5 实现认证路由 `src/auth/router.py`
    - POST `/auth/register`：接收 RegisterRequest → 调用 AuthService.register → 返回 UserResponse
    - POST `/auth/login`：接收 LoginRequest → 调用 AuthService.login → 返回 TokenResponse
    - POST `/auth/refresh`：接收 RefreshRequest → 调用 AuthService.refresh_token → 返回 TokenResponse
    - POST `/auth/logout`：需认证 → 调用 AuthService.logout
    - 通过 `asgi.env` 依赖获取 D1 和 KV 绑定
    - _Requirements: 1.1, 2.1, 3.1, 3.3_

- [x] 5. 实现用户路由和信息查询
  - [x] 5.1 实现用户路由 `src/users/router.py`
    - GET `/users/me`：需认证 → 从 D1 查询用户详情 → 返回 UserResponse（排除密码哈希）
    - GET `/users/me/geo`：需认证 → 从请求头 `CF-Connecting-IP` 获取 IP 地址 → 从 ASGI scope 中的 Cloudflare `cf` 对象获取地理位置信息（country、city、region、latitude、longitude、timezone）→ 返回 GeoResponse
    - 使用 `get_current_user` 依赖注入
    - 在 `src/auth/models.py` 中新增 `GeoResponse` 模型（ip, country, city, region, latitude, longitude, timezone，除 ip 外均可为 None）
    - _Requirements: 6.1, 6.2, 10.3, 10.4_

  - [ ]* 5.2 为用户信息查询编写属性测试
    - **Property 15: 用户信息响应包含必要字段且排除敏感数据**
    - **Validates: Requirements 6.1, 6.2**

  - [ ]* 5.3 为地理位置 API 编写属性测试
    - **Property 19: 地理位置 API 返回正确的请求来源信息**
    - **Validates: Requirements 10.3, 10.4**

- [x] 6. 集成和配置
  - [x] 6.1 更新 `src/main.py` 入口文件
    - 注册 auth_router 和 users_router
    - 移除现有的 `/` 路由（主页将由 `public/index.html` 静态文件提供）
    - 保留 `/greet` 路由
    - 添加应用启动时执行 D1 建表 SQL 的逻辑
    - _Requirements: 7.3, 10.4_

  - [x] 6.2 更新 `wrangler.jsonc` 配置绑定
    - 添加 D1 数据库绑定（binding: "DB"）
    - 添加 KV 命名空间绑定（binding: "TOKEN_BLACKLIST"）
    - 添加 JWT_SECRET 环境变量
    - 添加 GOOGLE_CLIENT_ID 环境变量
    - 添加 OAUTH_REDIRECT_BASE_URL 环境变量
    - 注释说明 GOOGLE_CLIENT_SECRET、JWT_SECRET 应通过 `wrangler secret put` 设置
    - _Requirements: 7.1, 7.2, 9.9_

  - [ ]* 6.3 为令牌刷新和注销流程编写属性测试
    - **Property 10: 令牌刷新返回新令牌**
    - **Property 11: 无效 refresh_token 被拒绝**
    - **Property 12: 注销后令牌失效（往返属性）**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4**

- [ ] 7. 检查点 - 确保核心认证功能正确
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 8. 实现 OAuth 登录服务和路由
  - [x] 8.1 实现 OAuth 服务 `src/auth/oauth_service.py`
    - 实现 `OAuthService` 类，包含 `get_authorization_url`、`handle_callback`、`_exchange_code`、`_get_user_info`、`_find_or_create_user` 方法
    - `get_authorization_url`：根据 provider 生成授权 URL，生成随机 state 并存入 KV（TTL=300s）
    - `_exchange_code`：使用 `fetch` API 向 OAuth Provider 发送 POST 请求交换 access_token
    - `_get_user_info`：使用 `fetch` API 调用 Provider 用户信息端点获取 email 和 name
    - `_find_or_create_user`：查询 oauth_accounts 表 → 若存在则返回关联用户 → 若不存在则按 email 查找用户或创建新用户 → 创建 oauth_account 记录
    - `handle_callback`：验证 state → 交换 code → 获取用户信息 → 查找/创建用户 → 生成 JWT tokens
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8, 9.9_

  - [ ]* 8.2 为 OAuth 服务编写属性测试
    - **Property 16: OAuth 授权 URL 包含正确参数**
    - **Property 17: OAuth 用户查找或创建一致性**
    - **Property 18: OAuth 账号关联持久化**
    - **Validates: Requirements 9.1, 9.4, 9.5, 9.7, 9.9**

  - [x] 8.3 实现 OAuth 路由 `src/auth/oauth_router.py`
    - GET `/auth/oauth/{provider}`：验证 provider 合法性 → 调用 OAuthService.get_authorization_url → 返回 302 重定向
    - GET `/auth/oauth/callback/{provider}`：接收 code 和 state 参数 → 调用 OAuthService.handle_callback → 成功时重定向到 `/oauth-callback.html` 并携带 tokens 参数 → 失败时重定向到 `/login.html?error=...`
    - 通过 `asgi.env` 依赖获取 D1、KV 和 OAuth 配置
    - _Requirements: 9.1, 9.2, 9.6, 9.9_

- [ ] 9. 实现认证前端页面
  - [x] 9.0 创建公共样式文件 `public/styles/common.css`
    - 使用纯 CSS 定义极简现代化风格的可复用样式类
    - 主色调使用 `slate-900`（近黑色），强调色 `#6366f1`（indigo），页面背景 `#fafafa`
    - 定义 `.m-card`（卡片：白色背景、`rounded-2xl`、微妙阴影、无边框）
    - 定义 `.m-input`（输入框：无边框、仅底部线条、聚焦时强调色底线）
    - 定义 `.m-button-primary`（主按钮：`slate-900` 背景、白色文字、`rounded-xl`、悬停提升阴影）
    - 定义 `.m-button-outline`（描边按钮：透明背景、细边框 `slate-200`、`rounded-xl`、悬停浅灰背景）
    - 定义 `.m-alert-error`（错误提示：红色系背景 `#fef2f2` + 红色左边框 + 状态图标，参考 Chakra UI Alert error 状态）、`.m-alert-success`（成功提示：绿色系背景 `#f0fdf4` + 绿色左边框 + 状态图标）、`.m-alert-warning`（警告提示：橙色系背景 + 橙色左边框 + 状态图标）、`.m-alert-info`（信息提示：蓝色系背景 + 蓝色左边框 + 状态图标）、`.m-alert-close`（关闭按钮）、`.m-divider`（分隔线）、`.m-link`（链接：`slate-900`、悬停下划线）
    - 实现全局 JavaScript 函数 `showAlert(message, type, duration)` 用于统一创建和展示 Alert 组件，`duration` 为自动消失时长（毫秒），默认 2000（2 秒），传 0 则不自动消失
    - 注意：所有消息提示统一通过页面内嵌的 Alert 组件展示（参考 Chakra UI Alert 设计规范），不使用浏览器 `alert()` 弹窗
    - _Requirements: 8.3_

  - [x] 9.1 重构登录页面 `public/login.html` 使用极简现代化风格
    - 引用公共样式文件 `<link rel="stylesheet" href="/styles/common.css">`
    - 使用 TailwindCSS CDN（`<script src="https://cdn.tailwindcss.com"></script>`）和 Inter 字体
    - 将样式替换为 `common.css` 中定义的 `.m-card`、`.m-input`、`.m-button-primary`、`.m-button-outline`、`.m-link` 等样式类，消息提示通过 Alert 组件（`.m-alert` 系列样式类）展示
    - 极简居中卡片式布局，大量留白，包含邮箱和密码输入框、登录按钮
    - 包含 Google 第三方登录按钮，点击跳转到 `/auth/oauth/google`
    - 包含"没有账号？注册"链接，指向 `/register.html`
    - JavaScript：表单提交调用 `/auth/login` API，成功后存储 tokens 到 localStorage 并跳转主页，失败时通过 Alert 组件（error 状态）显示错误信息
    - 检查 URL 参数中的 error 信息并通过 Alert 组件（error 状态）显示（用于 OAuth 失败回调）
    - _Requirements: 8.1, 8.3, 8.4, 8.6, 8.7, 8.9_

  - [x] 9.2 重构注册页面 `public/register.html` 使用极简现代化风格
    - 引用公共样式文件 `<link rel="stylesheet" href="/styles/common.css">`
    - 使用 TailwindCSS CDN，与登录页面风格一致
    - 将样式替换为 `common.css` 中定义的样式类
    - 极简居中卡片式布局，大量留白，包含用户名、邮箱、密码、确认密码输入框和注册按钮
    - 包含 Google 第三方登录按钮
    - 包含"已有账号？登录"链接，指向 `/login.html`
    - JavaScript：提交前验证密码与确认密码一致性（不一致时通过 Alert 组件 error 状态提示），调用 `/auth/register` API，成功后通过 Alert 组件 success 状态提示并跳转到登录页面，失败时通过 Alert 组件 error 状态显示错误信息
    - _Requirements: 8.2, 8.3, 8.5, 8.6, 8.7, 8.8, 8.9_

  - [x] 9.3 创建 OAuth 回调中转页面 `public/oauth-callback.html`
    - 引用公共样式文件 `<link rel="stylesheet" href="/styles/common.css">`
    - 从 URL 参数中提取 access_token 和 refresh_token
    - 存储 tokens 到 localStorage
    - 自动跳转到主页
    - 处理错误参数，通过 Alert 组件（error 状态）显示错误信息或跳转到登录页面
    - _Requirements: 9.10_

  - [x] 9.4 实现已登录用户访问登录/注册页面时重定向到首页
    - 在 `public/login.html` 的 `<script>` 顶部（表单逻辑之前）添加 `access_token` 检查，若存在则 `window.location.replace('/')` 重定向到首页
    - 在 `public/register.html` 的 `<script>` 顶部（表单逻辑之前）添加相同的 `access_token` 检查和重定向逻辑
    - 重定向检查在 DOM 交互逻辑之前同步执行，确保已登录用户不会看到表单闪烁
    - _Requirements: 11.1, 11.2, 11.3_

- [x] 10. 实现用户主页
  - [x] 10.1 实现用户主页 `public/index.html`
    - 替换现有的 Hello World 页面为用户主页
    - 引用公共样式文件 `<link rel="stylesheet" href="/styles/common.css">` 和 TailwindCSS CDN
    - 采用 Naive UI 风格居中卡片式布局，与登录/注册页面风格一致
    - 页面加载时检查 localStorage 中是否存在 `access_token`，若不存在则跳转到 `/login.html`
    - 调用 `/users/me` API（携带 Bearer token）获取并显示用户基本信息（用户名、邮箱、角色、注册时间）
    - 调用 `/users/me/geo` API（携带 Bearer token）获取并显示 IP 地址和地理位置信息（国家、城市、时区）
    - 加载数据时显示 loading 状态，API 失败时通过 Alert 组件（error 状态）显示错误提示并提供重试按钮
    - 若 API 返回 401，清除 localStorage 中的 tokens 并跳转到 `/login.html`
    - 退出登录按钮：点击后调用 `/auth/logout` API（POST，携带 access_token 和 refresh_token），清除 localStorage，跳转到 `/login.html`
    - _Requirements: 10.1, 10.2, 10.3, 10.5, 10.6, 10.7_
  - [x] 在主页界面，ip地址显示为:unknown，且国家地区信息未正确显示出来

  - [x] 10.2 重构主页为认证成功页面
    - 将 `public/index.html` 从详细用户信息展示页改为简洁的认证成功页面
    - 显示"认证成功"提示信息和当前登录用户的用户名
    - 保留退出登录按钮（调用 `/auth/logout` API，清除 localStorage，跳转到 `/login.html`）
    - 保留认证检查逻辑（无 token 跳转登录页，401 清除 tokens 跳转登录页）
    - 移除用户详细信息（邮箱、角色、注册时间）和地理位置信息展示
    - 通过 `/users/me` API 仅获取用户名用于欢迎信息展示
    - 采用极简现代化风格，与其他页面一致
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

- [x] 13. 实现个人信息页
  - [x] 13.1 创建个人信息页 `public/profile.html`
    - 引用公共样式文件 `<link rel="stylesheet" href="/styles/common.css">` 和 TailwindCSS CDN
    - 采用极简现代化风格居中卡片式布局，与其他页面风格一致
    - 页面加载时检查 localStorage 中是否存在 `access_token`，若不存在则跳转到 `/login.html`
    - 调用 `/users/me` API（携带 Bearer token）获取并显示用户基本信息（用户名、邮箱、角色、注册时间）
    - 调用 `/users/me/geo` API（携带 Bearer token）获取并显示 IP 地址和地理位置信息（国家、城市、时区）
    - 加载数据时显示 loading 状态，API 失败时通过 Alert 组件（error 状态）显示错误提示并提供重试按钮
    - 若 API 返回 401，清除 localStorage 中的 tokens 并跳转到 `/login.html`
    - 退出登录按钮：位于页面顶部右侧，点击后调用 `/auth/logout` API（POST，携带 access_token 和 refresh_token），清除 localStorage，跳转到 `/login.html`
    - 该页面仅通过手动输入 URL `/profile.html` 访问，主页和其他页面不提供导航链接
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 12.8_

- [x] 11. 集成 OAuth 路由到主应用
  - [x] 11.1 更新 `src/main.py` 注册 OAuth 路由
    - 导入并注册 oauth_router
    - 确保 D1 建表 SQL 包含 oauth_accounts 表
    - _Requirements: 9.1, 9.2_

- [ ] 12. 最终检查点 - 确保所有功能正确
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 14. 优化第三方平台认证登录
  - [x] 14.1 升级 oauth_accounts 表结构
    - 修改 `src/schema.sql` 和 `migrations/0001_init.sql`，为 oauth_accounts 表新增字段：provider_email、provider_name、provider_avatar_url、access_token_expires_at、updated_at
    - 参考阿里巴巴、腾讯等顶级互联网公司的第三方平台账号管理方案，记录完整的第三方账号信息
    - _Requirements: 9.7_

  - [x] 14.2 更新 UserRepository 支持新的 oauth_accounts 字段
    - 修改 `src/users/repository.py` 中的 `create_oauth_account` 方法，支持传入 provider_email、provider_name、provider_avatar_url、access_token_expires_at 参数
    - 新增 `update_oauth_account` 方法，用于每次 OAuth 登录时更新第三方账号信息（显示名称、头像、过期时间等）
    - 新增 `update_password` 方法，用于 OAuth 用户设置密码
    - 更新 `get_oauth_accounts_by_user` 方法，返回包含新字段的完整 OAuth 账号信息
    - _Requirements: 9.7, 9.10, 13.4_

  - [x] 14.3 更新 OAuth 服务，使 token 过期时间与 Google 保持一致
    - 修改 `src/auth/oauth_service.py` 中的 `_exchange_code` 方法，从 Google 令牌响应中提取 `expires_in` 字段
    - 修改 `handle_callback` 方法，使用 Google 返回的 `expires_in`（通常为 3600 秒 = 60 分钟）作为系统 access_token 的过期时间
    - 在 `_find_or_create_user` 和 `handle_callback` 中调用 `create_oauth_account` / `update_oauth_account` 传入完整的第三方账号信息
    - 在 `_get_user_info` 中提取 Google 返回的头像 URL（picture 字段）
    - _Requirements: 9.9, 9.10_

  - [x] 14.4 新增 Pydantic 模型和 API 端点
    - 在 `src/auth/models.py` 中新增 `SetPasswordRequest`、`OAuthAccountInfo`、`UserDetailResponse` 模型
    - 在 `src/users/router.py` 中新增 `GET /users/me/detail` 端点，返回用户详细信息（含 has_password 和 oauth_accounts 列表）
    - 在 `src/users/router.py` 中新增 `PUT /users/me/password` 端点，允许 OAuth 用户设置密码
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.6_

  - [x] 14.5 更新个人信息页面显示 Google 账号信息和设置密码功能
    - 修改 `public/profile.html`，调用 `/users/me/detail` API 替代 `/users/me` API
    - 新增 Google 账号信息展示区域（头像、显示名称、邮箱）
    - 新增设置密码表单（仅在 has_password 为 false 时显示）
    - 已设置密码时显示"已设置密码"状态提示
    - 设置密码表单包含密码和确认密码输入框，提交前验证一致性和长度
    - _Requirements: 12.9, 12.10, 12.11, 12.12_

- [x] 15. 优化个人信息页面 — 分栏导航布局
  - [x] 15.1 在 `public/styles/common.css` 中新增 Tab 导航样式
    - 新增 `.m-tabs` 容器样式（flex 布局、底部边线 `border-bottom 1px solid #e2e8f0`）
    - 新增 `.m-tab` 单项样式（`cursor-pointer`、`pb-3`、`text-sm`、`slate-400` 文字、`transition-all 0.2s`、底部 2px 透明边线）
    - 新增 `.m-tab:hover` 悬停样式（`slate-600` 文字）
    - 新增 `.m-tab-active` 激活样式（`#6366f1` indigo-500 底线、`slate-900` 文字、`font-medium`）
    - 新增 `.m-tab-panel` 和 `.m-tab-panel-active` 内容面板样式
    - 新增 `.m-avatar` 和 `.m-avatar-placeholder` 头像样式
    - _Requirements: 12.6, 12.15_

  - [x] 15.2 重构 `public/profile.html` 为分栏导航布局
    - 将页面宽度从 `max-w-md` 扩展为 `max-w-2xl`
    - 重构顶部区域：左侧显示用户头像（OAuth 头像或首字母占位符）+ 用户名 + 副标题，右侧退出按钮
    - 新增选项卡导航栏（「基本信息」「账号安全」「网络信息」），默认激活「基本信息」
    - 将原有多张卡片内容重组为三个 Tab 面板，使用单张 `.m-card` 承载
    - 「基本信息」面板：用户名、邮箱、角色、注册时间
    - 「账号安全」面板：关联的第三方账号 + 设置密码功能
    - 「网络信息」面板：IP 地址、国家、城市、时区
    - 实现 Tab 切换逻辑（纯前端 JS，切换 hidden 类，无需重新请求 API）
    - 保留所有现有功能（认证检查、退出登录、设置密码、错误处理、重试按钮）
    - _Requirements: 12.1, 12.2, 12.9, 12.10, 12.11, 12.12, 12.13, 12.14, 12.15, 12.16_

- [x] 16. 优化个人信息页面 — 顶部区域固定布局
  - [x] 16.1 在 `public/styles/common.css` 中新增 `.m-profile-header` 样式
    - 新增 `.m-profile-header` 样式类：`position: sticky`、`top: 1.5rem`、`z-index: 10`、白色背景、圆角（`rounded-2xl`）、微妙阴影，与 `.m-card` 风格一致
    - 该样式用于包裹个人信息页的用户信息行和选项卡导航栏，使其在页面滚动时保持固定可见
    - _Requirements: 12.17_

  - [x] 16.2 重构 `public/profile.html` 顶部区域为固定布局
    - 将用户头像/用户名/退出按钮行和选项卡导航栏整合到同一个 `.m-profile-header` 容器内
    - 顶部固定卡片内包含：用户信息行（头像 + 用户名 + 退出按钮）和 Tab 导航栏
    - 下方内容卡片（`.m-card`）紧接顶部卡片，`margin-top: 0.75rem`，形成连续垂直布局
    - 移除 `body` 上的 `flex items-center justify-center`，改为 `flex justify-center items-start`，确保内容从顶部开始垂直排列
    - 保留所有现有功能不变
    - _Requirements: 12.15, 12.16, 12.17_

- [x] 执行命令deploy命令，将当前worker部署到cloudflare

- [x] 17. 实现用户登录历史记录功能
  - [x] 17.1 更新数据库 schema 和创建迁移文件
    - 在 `src/schema.sql` 中新增 `login_history` 表（id、user_id、action、method、ip、country、city、region、user_agent、created_at）
    - 创建 `migrations/0003_login_history.sql` 迁移文件
    - 为 user_id 和 (user_id, created_at) 建立索引
    - _Requirements: 14.1, 14.5, 14.7_

  - [x] 17.2 实现登录历史仓库 `src/users/login_history_repository.py`
    - 实现 `LoginHistoryRepository` 类，接受 D1 binding
    - 实现 `create_record` 方法：插入登录/登出记录，使用 `uuid.uuid4()` 生成 ID
    - 实现 `get_by_user` 方法：分页查询用户登录历史，按 created_at 倒序排列
    - 实现 `count_by_user` 方法：查询用户登录历史总数
    - _Requirements: 14.1, 14.5, 14.6, 14.7_

  - [x] 17.3 新增 Pydantic 模型
    - 在 `src/auth/models.py` 中新增 `LoginHistoryRecord` 模型（id、action、method、ip、country、city、region、user_agent、created_at）
    - 在 `src/auth/models.py` 中新增 `LoginHistoryResponse` 模型（records、total、page、page_size）
    - _Requirements: 14.6_

  - [x] 17.4 在登录流程中记录登录历史
    - 修改 `src/auth/router.py` 的 `login` 端点，在登录成功后调用 `LoginHistoryRepository.create_record` 记录密码登录历史（action="login"、method="password"），从 Request 对象获取 IP 和地理位置信息
    - 修改 `src/auth/oauth_router.py` 的 `oauth_callback` 端点，在 OAuth 登录成功后调用 `LoginHistoryRepository.create_record` 记录 OAuth 登录历史（action="login"、method="oauth:{provider}"），从 Request 对象获取 IP 和地理位置信息
    - _Requirements: 14.2, 14.3, 14.8_

  - [x] 17.5 在登出流程中记录登出历史
    - 修改 `src/auth/router.py` 的 `logout` 端点，在登出成功后调用 `LoginHistoryRepository.create_record` 记录登出历史（action="logout"、method=None），从 Request 对象获取 IP 和地理位置信息
    - _Requirements: 14.4, 14.8_

  - [x] 17.6 实现登录历史查询 API 端点
    - 在 `src/users/router.py` 中新增 `GET /users/me/login-history` 端点
    - 支持 page（默认 1）和 page_size（默认 20，最大 100）查询参数
    - 返回 `LoginHistoryResponse`，包含分页记录、总数、当前页码和每页大小
    - _Requirements: 14.6_

  - [x] 17.7 更新 `src/main.py` 确保 login_history 表在启动时创建
    - 确保 `_init_schema` 函数执行的 schema.sql 包含 login_history 表的建表语句
    - 无需额外修改，因为 schema.sql 已在 17.1 中更新
    - _Requirements: 14.1_

## 备注

- 标记 `*` 的任务为可选任务，可跳过以加速 MVP 开发
- 每个任务引用了具体的需求编号以确保可追溯性
- 检查点确保增量验证
- 属性测试验证通用正确性属性，单元测试验证具体示例和边界情况
- D1 和 KV 的实际 database_id 和 namespace_id 需要用户通过 `wrangler d1 create` 和 `wrangler kv namespace create` 命令创建后填入
- OAuth client_id 和 client_secret 需要在 Google Cloud Console 中创建应用后获取
- GOOGLE_CLIENT_SECRET 和 JWT_SECRET 应通过 `wrangler secret put` 设置为 Secrets
- 前端页面使用 TailwindCSS CDN，采用极简现代化设计风格（slate 色调、大圆角、底线输入框、大量留白），公共样式统一在 `public/styles/common.css` 中维护，消息提示通过页面内嵌的 Alert 组件展示（参考 Chakra UI Alert 设计规范，支持 error/success/warning/info 四种状态，默认 2 秒后自动消失，可通过 duration 参数自定义时长），无需本地构建步骤
- OAuth 回调 URL 需要在各 Provider 的开发者控制台中配置为 `{OAUTH_REDIRECT_BASE_URL}/auth/oauth/callback/{provider}`
- 用户主页（`public/index.html`）为认证成功页面，登录后自动跳转到此页面，仅显示认证成功信息和用户名
- 个人信息页（`public/profile.html`）展示用户详细信息和地理位置，仅通过手动输入 URL 访问
- 地理位置信息通过 Cloudflare Workers 的 `request.cf` 对象和 `CF-Connecting-IP` 请求头获取，本地开发时这些值可能不可用
