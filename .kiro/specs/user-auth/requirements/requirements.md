# 需求文档

## 简介

为基于 Cloudflare Workers (Python) + FastAPI 的项目 `cloudflare-auth` 实现用户认证与授权功能。该功能包括用户注册、登录、JWT 令牌管理以及基于角色的权限验证。系统使用 Cloudflare D1 作为用户数据持久化存储，使用 KV 存储管理令牌黑名单。

## 术语表

- **Auth_System**: 用户认证与授权系统，负责处理注册、登录、令牌管理和权限验证
- **User**: 系统中的注册用户实体，包含用户名、邮箱、密码哈希和角色信息
- **JWT_Token**: JSON Web Token，用于用户身份验证的令牌，包含用户身份和过期时间
- **Password_Hasher**: 密码哈希处理组件，负责密码的加密和验证
- **Auth_Middleware**: 认证中间件，负责拦截请求并验证用户身份
- **D1_Database**: Cloudflare D1 SQL 数据库，用于存储用户数据
- **KV_Store**: Cloudflare KV 键值存储，用于管理令牌黑名单
- **Role**: 用户角色，用于权限控制（如 "user"、"admin"）
- **Auth_UI**: 认证前端界面，包括注册页面和登录页面，采用极简现代化设计风格（无边框输入框、大量留白、中性色调、微妙动效），使用 TailwindCSS 实现，公共样式通过 `public/styles/common.css` 统一维护。所有消息提示（错误、成功、警告等）统一通过页面内嵌的 Alert 组件展示（参考 Chakra UI Alert 设计规范，包含 status 图标、标题、描述文本和关闭按钮），Alert 组件样式与当前极简现代化 UI 风格统一（slate/indigo 色调、大圆角、微妙阴影、平滑过渡动效），通过 `public/styles/common.css` 中的 `.m-alert` 系列样式类实现。Alert 组件支持通过 `duration` 参数设置显示时长（毫秒），默认显示 2 秒后自动消失，传 0 则不自动消失
- **OAuth_Provider**: 第三方 OAuth 2.0 认证提供商，目前支持 Google
- **OAuth_Flow**: OAuth 2.0 授权码流程，用于第三方登录的标准认证流程
- **Auth_Page_Router**: 前端页面路由，负责在登录、注册和 OAuth 回调页面之间导航
- **Home_Page**: 用户主页面，登录成功后展示用户信息（包括 IP 地址和地理位置）并提供退出登录功能
- **Geo_Info**: 用户地理位置信息，通过 Cloudflare Workers 的 `request.cf` 对象和 `CF-Connecting-IP` 请求头获取
- **Profile_Page**: 个人信息页面（`/profile.html`），展示用户详细信息（用户名、邮箱、角色、注册时间）和地理位置信息（IP、国家、城市），需手动输入 URL 访问，不在主页或其他页面提供导航链接
- **Login_History**: 用户登录历史记录表，记录用户的登录和登出操作，包含 IP 地址、地理位置、登录方式等信息，用于安全审计和统计分析。兼容系统密码登录和第三方 OAuth 登录

## 需求

### 需求 1：用户注册

**用户故事：** 作为一个新用户，我希望能够注册账号，以便获得系统访问权限。

#### 验收标准

1. WHEN 用户提交包含用户名、邮箱和密码的注册请求, THE Auth_System SHALL 验证输入数据格式并创建新用户记录存储到 D1_Database 中
2. WHEN 用户提交的邮箱已存在于 D1_Database 中, THE Auth_System SHALL 返回明确的错误信息指示邮箱已被注册
3. WHEN 用户提交的用户名已存在于 D1_Database 中, THE Auth_System SHALL 返回明确的错误信息指示用户名已被占用
4. WHEN 用户注册成功, THE Auth_System SHALL 使用 Password_Hasher 对密码进行哈希处理后再存储，原始密码不得保留在任何存储中
5. WHEN 用户提交的密码长度少于 8 个字符, THE Auth_System SHALL 拒绝注册并返回密码强度不足的错误信息
6. WHEN 用户提交的邮箱格式无效, THE Auth_System SHALL 拒绝注册并返回邮箱格式错误的提示信息
7. WHEN 用户注册成功, THE Auth_System SHALL 为新用户分配默认角色 "user" 并返回用户信息（不含密码）

### 需求 2：用户登录

**用户故事：** 作为一个已注册用户，我希望能够登录系统，以便获取访问令牌进行后续操作。

#### 验收标准

1. WHEN 用户提交正确的邮箱和密码, THE Auth_System SHALL 验证凭据并返回一个有效的 JWT_Token
2. WHEN 用户提交的邮箱不存在于 D1_Database 中, THE Auth_System SHALL 返回统一的"凭据无效"错误信息
3. WHEN 用户提交的密码与存储的哈希不匹配, THE Auth_System SHALL 返回统一的"凭据无效"错误信息
4. WHEN 登录成功, THE Auth_System SHALL 在 JWT_Token 中包含用户 ID、用户名、角色和过期时间
5. WHEN 登录成功, THE Auth_System SHALL 同时返回 access_token 和 refresh_token，access_token 有效期为 15 分钟，refresh_token 有效期为 7 天

### 需求 3：令牌管理

**用户故事：** 作为一个已登录用户，我希望能够刷新和注销令牌，以便维持会话安全。

#### 验收标准

1. WHEN 用户使用有效的 refresh_token 请求刷新, THE Auth_System SHALL 返回新的 access_token 和 refresh_token
2. WHEN 用户使用过期或无效的 refresh_token 请求刷新, THE Auth_System SHALL 拒绝请求并返回令牌无效的错误信息
3. WHEN 用户请求注销, THE Auth_System SHALL 将当前 access_token 和 refresh_token 加入 KV_Store 黑名单
4. WHEN 收到携带已列入黑名单的令牌的请求, THE Auth_System SHALL 拒绝该请求并返回令牌已失效的错误信息

### 需求 4：权限验证中间件

**用户故事：** 作为一个系统开发者，我希望有统一的权限验证机制，以便保护需要认证的 API 端点。

#### 验收标准

1. WHEN 请求携带有效的 JWT_Token 访问受保护端点, THE Auth_Middleware SHALL 解析令牌并将用户信息注入请求上下文
2. WHEN 请求未携带 JWT_Token 访问受保护端点, THE Auth_Middleware SHALL 返回 401 未授权错误
3. WHEN 请求携带过期的 JWT_Token, THE Auth_Middleware SHALL 返回 401 错误并提示令牌已过期
4. WHEN 请求携带格式错误的 JWT_Token, THE Auth_Middleware SHALL 返回 401 错误并提示令牌无效
5. WHERE 端点配置了角色要求, THE Auth_Middleware SHALL 验证用户角色是否满足要求，角色不足时返回 403 禁止访问错误

### 需求 5：密码安全

**用户故事：** 作为一个系统管理员，我希望用户密码得到安全处理，以便防止数据泄露时密码被破解。

#### 验收标准

1. THE Password_Hasher SHALL 使用 bcrypt 或等效的安全哈希算法对密码进行哈希处理
2. WHEN 验证密码时, THE Password_Hasher SHALL 通过比较哈希值来验证，验证过程不涉及明文密码的存储或日志记录
3. THE Password_Hasher SHALL 为每个密码生成唯一的盐值

### 需求 6：用户信息查询

**用户故事：** 作为一个已登录用户，我希望能够查看自己的个人信息，以便确认账户状态。

#### 验收标准

1. WHEN 已认证用户请求查看个人信息, THE Auth_System SHALL 返回该用户的用户名、邮箱、角色和注册时间
2. THE Auth_System SHALL 在返回用户信息时排除密码哈希等敏感字段

### 需求 7：数据存储配置

**用户故事：** 作为一个系统开发者，我希望正确配置 Cloudflare 存储绑定，以便认证系统能够持久化数据。

#### 验收标准

1. THE Auth_System SHALL 通过 wrangler.jsonc 配置 D1_Database 绑定用于存储用户数据
2. THE Auth_System SHALL 通过 wrangler.jsonc 配置 KV_Store 绑定用于管理令牌黑名单
3. WHEN Auth_System 启动时, THE Auth_System SHALL 确保 D1_Database 中存在所需的用户表结构


### 需求 8：认证前端页面

**用户故事：** 作为一个用户，我希望有美观简洁的注册和登录页面，以便通过浏览器完成账号注册和登录操作。

#### 验收标准

1. WHEN 用户访问 `/login.html` 页面, THE Auth_UI SHALL 展示一个包含邮箱和密码输入框及登录按钮的登录表单
2. WHEN 用户访问 `/register.html` 页面, THE Auth_UI SHALL 展示一个包含用户名、邮箱、密码和确认密码输入框及注册按钮的注册表单
3. THE Auth_UI SHALL 使用 TailwindCSS CDN 实现响应式布局，采用极简现代化设计风格（无边框底线输入框、大量留白、中性色调 slate 系、微妙过渡动效、扁平化设计），所有页面的公共样式（按钮、输入框、卡片、错误提示等）统一在 `public/styles/common.css` 中维护，各 HTML 页面通过 `<link>` 引用该文件
4. WHEN 用户在登录页面提交有效凭据, THE Auth_UI SHALL 调用 `/auth/login` API 并在成功后将令牌存储到 localStorage 中，然后跳转到主页
5. WHEN 用户在注册页面提交有效信息, THE Auth_UI SHALL 调用 `/auth/register` API 并在成功后自动跳转到登录页面
6. WHEN API 返回错误响应或操作成功需要通知用户时, THE Auth_UI SHALL 统一通过页面内嵌的 Alert 组件显示消息提示信息（参考 Chakra UI Alert 设计规范，支持 error、success、warning、info 四种状态），Alert 组件样式与当前极简现代化 UI 风格统一，通过 `common.css` 中的 `.m-alert` 系列样式类实现。Alert 组件支持通过 `duration` 参数设置显示时长（毫秒），默认显示 2 秒后自动消失，传 0 则不自动消失
7. WHEN 用户在登录页面点击"注册"链接, THE Auth_UI SHALL 导航到注册页面；WHEN 用户在注册页面点击"登录"链接, THE Auth_UI SHALL 导航到登录页面
8. WHEN 用户在注册表单中输入的密码与确认密码不一致, THE Auth_UI SHALL 在提交前通过页面内嵌的 Alert 组件（error 状态）显示密码不匹配的错误提示
9. THE Auth_UI SHALL 在登录和注册页面展示 Google 第三方登录按钮，按钮样式与整体页面风格一致

### 需求 9：第三方 OAuth 登录

**用户故事：** 作为一个用户，我希望能够使用 Google 账号登录，以便无需创建新密码即可快速访问系统。

#### 验收标准

1. WHEN 用户点击 Google 登录按钮, THE Auth_System SHALL 将用户重定向到 Google OAuth 2.0 授权端点，携带正确的 client_id、redirect_uri 和 scope 参数
2. WHEN OAuth_Provider 回调携带授权码, THE Auth_System SHALL 使用授权码向 OAuth_Provider 交换 access_token
3. WHEN Auth_System 获取到 OAuth access_token, THE Auth_System SHALL 调用 OAuth_Provider 的用户信息 API 获取用户邮箱、显示名称、头像 URL 等信息
4. WHEN OAuth 登录的用户邮箱已存在于 D1_Database 中, THE Auth_System SHALL 将该 OAuth 账号关联到已有用户并返回 JWT_Token
5. WHEN OAuth 登录的用户邮箱不存在于 D1_Database 中, THE Auth_System SHALL 自动创建新用户（使用 OAuth 提供的邮箱和显示名称）并返回 JWT_Token
6. IF OAuth_Provider 返回错误或用户拒绝授权, THEN THE Auth_System SHALL 将用户重定向回登录页面并显示相应的错误信息
7. THE Auth_System SHALL 在 D1_Database 的 oauth_accounts 表中存储用户的 OAuth 提供商标识、提供商用户 ID、显示名称、头像 URL、邮箱和 access_token 过期时间等详细信息，以支持同一用户关联多个 OAuth 账号。该表设计参考阿里巴巴、腾讯等顶级互联网公司的第三方平台账号管理方案
8. THE Auth_System SHALL 将 OAuth client_id 和 client_secret 通过 Cloudflare 环境变量或 Secrets 管理，不硬编码在代码中
9. WHEN OAuth 回调处理成功, THE Auth_System SHALL 生成系统内部的 JWT_Token（access_token 和 refresh_token），其中 access_token 的过期时间应与 Google OAuth 返回的 expires_in 保持一致（通常为 1 小时），refresh_token 保持系统默认的 7 天有效期，并通过 URL 参数或页面脚本传递给前端
10. WHEN OAuth 回调处理成功, THE Auth_System SHALL 在每次登录时更新 oauth_accounts 表中的 access_token 过期时间、显示名称和头像 URL 等信息，确保第三方账号信息保持最新


### 需求 11：已登录用户页面重定向

**用户故事：** 作为一个已登录用户，当我访问登录页面或注册页面时，我希望被自动重定向到首页，以避免重复登录或注册。

#### 验收标准

1. WHEN 已持有有效 access_token 的用户访问 `/login.html` 页面, THE Auth_UI SHALL 在页面加载时检测 localStorage 中的 access_token，并立即将用户重定向到首页（`/`）
2. WHEN 已持有有效 access_token 的用户访问 `/register.html` 页面, THE Auth_UI SHALL 在页面加载时检测 localStorage 中的 access_token，并立即将用户重定向到首页（`/`）
3. WHEN 用户未持有 access_token 访问登录或注册页面, THE Auth_UI SHALL 正常展示登录或注册表单，不进行任何重定向

### 需求 10：用户主页（认证成功页）

**用户故事：** 作为一个已登录用户，我希望登录成功后能看到一个简洁的认证成功页面，以便确认登录状态。

#### 验收标准

1. WHEN 用户登录成功, THE Auth_UI SHALL 将用户跳转到主页面（`/` 或 `/index.html`）
2. WHEN 已认证用户访问主页面, THE Home_Page SHALL 显示"认证成功"的提示信息和当前登录用户的用户名
3. WHEN 已认证用户访问主页面, THE Home_Page SHALL 提供退出登录按钮
4. WHEN 用户点击主页面的退出登录按钮, THE Home_Page SHALL 调用后端 `/auth/logout` API 使令牌失效，清除 localStorage 中的 tokens，并将用户跳转到登录页面
5. WHEN 未持有有效 tokens 的用户访问主页面, THE Home_Page SHALL 自动将用户跳转到登录页面
6. IF 获取用户信息的 API 请求失败, THEN THE Home_Page SHALL 通过页面内嵌的 Alert 组件（error 状态）显示友好的错误提示，Alert 组件样式与当前极简现代化 UI 风格统一

### 需求 12：个人信息页

**用户故事：** 作为一个已登录用户，我希望能够通过手动输入 URL 访问个人信息页面，以便查看我的详细账户信息和地理位置。

#### 验收标准

1. WHEN 已认证用户访问 `/profile.html` 页面, THE Profile_Page SHALL 显示当前登录用户的基本信息，包括用户名、邮箱、角色和注册时间
2. WHEN 已认证用户访问 `/profile.html` 页面, THE Profile_Page SHALL 通过后端 API 获取并显示用户的 IP 地址和所在地区信息（国家、城市）
3. THE Auth_System SHALL 提供一个获取用户地理位置信息的 API 端点，利用 Cloudflare Workers 的 `request.cf` 对象获取地理位置数据，通过 `CF-Connecting-IP` 请求头获取客户端 IP 地址
4. WHEN 未持有有效 tokens 的用户访问 `/profile.html` 页面, THE Profile_Page SHALL 自动将用户跳转到登录页面
5. IF 获取用户信息或地理位置信息的 API 请求失败, THEN THE Profile_Page SHALL 通过页面内嵌的 Alert 组件（error 状态）显示友好的错误提示并提供重试选项，Alert 组件样式与当前极简现代化 UI 风格统一
6. THE Profile_Page SHALL 采用与其他页面一致的极简现代化设计风格（TailwindCSS + common.css）
7. THE Profile_Page SHALL 提供退出登录按钮，行为与主页退出按钮一致
8. THE Profile_Page SHALL 不在主页或其他页面提供导航链接，仅通过手动输入 URL `/profile.html` 访问
9. WHEN 已认证用户通过 Google OAuth 登录, THE Profile_Page SHALL 显示关联的 Google 账号信息，包括 Google 显示名称、头像和邮箱
10. WHEN 已认证用户通过 OAuth 登录且未设置密码, THE Profile_Page SHALL 显示"设置密码"表单，允许用户设置密码以注册为系统普通用户
11. WHEN OAuth 用户在个人信息页面提交设置密码请求, THE Auth_System SHALL 验证密码强度（≥8 位）并使用 Password_Hasher 对密码进行哈希处理后更新到 D1_Database 中，使该用户成为同时支持密码登录和 OAuth 登录的普通用户
12. WHEN 已设置密码的 OAuth 用户访问个人信息页面, THE Profile_Page SHALL 不再显示"设置密码"表单，而是显示"已设置密码"的状态提示
13. THE Profile_Page SHALL 使用分栏导航（Tab）布局，将页面内容划分为多个选项卡，用户可通过点击选项卡切换查看不同内容区域。选项卡包括：「基本信息」（用户名、邮箱、角色、注册时间）、「账号安全」（关联的第三方账号信息、设置密码功能）、「网络信息」（IP 地址、地理位置信息）
14. THE Profile_Page SHALL 默认显示「基本信息」选项卡，选项卡切换时无需重新加载页面，通过前端 JavaScript 控制内容区域的显示/隐藏
15. THE Profile_Page SHALL 使用宽屏布局（max-w-2xl），选项卡导航栏位于内容区域顶部，采用水平排列的底线高亮风格（active tab 使用 indigo-500 底线 + 深色文字，inactive tab 使用 slate-400 文字），与整体极简现代化风格统一
16. THE Profile_Page SHALL 优化空间布局，页面顶部显示用户头像（若有 OAuth 头像则使用，否则显示用户名首字母占位符）和用户名，退出登录按钮位于顶部右侧，选项卡内容区域使用单张卡片承载，减少视觉碎片
17. THE Profile_Page SHALL 将顶部区域（用户头像、用户名、退出按钮）和选项卡导航栏整合到同一张卡片容器内，与下方选项卡内容面板形成一个连续的垂直布局整体。顶部区域在页面滚动时保持固定（sticky），确保用户始终可见导航和退出操作。整体内容区域保持垂直排列，避免视觉断裂

### 需求 13：OAuth 用户设置密码

**用户故事：** 作为一个通过第三方 OAuth 登录的用户，我希望能够设置密码，以便同时支持密码登录和 OAuth 登录。

#### 验收标准

1. THE Auth_System SHALL 提供 `PUT /users/me/password` API 端点，允许已认证的 OAuth 用户设置密码
2. WHEN OAuth 用户提交设置密码请求, THE Auth_System SHALL 验证该用户当前未设置密码（password_hash 为空），若已设置密码则返回错误
3. WHEN OAuth 用户提交的密码长度少于 8 个字符, THE Auth_System SHALL 拒绝请求并返回密码强度不足的错误信息
4. WHEN OAuth 用户成功设置密码, THE Auth_System SHALL 使用 Password_Hasher 对密码进行哈希处理后更新到 D1_Database 中
5. WHEN OAuth 用户成功设置密码后, THE Auth_System SHALL 允许该用户同时使用邮箱密码登录和 OAuth 登录
6. THE Auth_System SHALL 提供 `GET /users/me/detail` API 端点，返回用户详细信息，包括是否已设置密码（has_password 布尔值）和关联的 OAuth 账号列表

### 需求 14：用户登录历史记录

**用户故事：** 作为一个系统管理员或用户，我希望能够记录和查看登录/登出历史，以便进行安全审计和统计分析。

#### 验收标准

1. THE Auth_System SHALL 在 D1_Database 中创建 `login_history` 表，用于记录用户的登录和登出操作历史
2. WHEN 用户通过邮箱密码登录成功, THE Auth_System SHALL 在 login_history 表中插入一条登录记录，包含用户 ID、登录方式（password）、操作类型（login）、IP 地址和地理位置信息
3. WHEN 用户通过 OAuth 第三方平台登录成功, THE Auth_System SHALL 在 login_history 表中插入一条登录记录，包含用户 ID、登录方式（oauth:{provider}，如 oauth:google）、操作类型（login）、IP 地址和地理位置信息
4. WHEN 用户执行登出操作, THE Auth_System SHALL 在 login_history 表中插入一条登出记录，包含用户 ID、操作类型（logout）、IP 地址和地理位置信息
5. THE login_history 表 SHALL 记录以下字段：记录 ID、用户 ID、操作类型（login/logout）、登录方式（password/oauth:google 等）、IP 地址、国家、城市、地区、用户代理（User-Agent）、操作时间
6. THE Auth_System SHALL 提供 `GET /users/me/login-history` API 端点，允许已认证用户查询自己的登录历史记录，支持分页查询（page、page_size 参数，默认 page=1、page_size=20）
7. THE login_history 表 SHALL 通过 user_id 和 created_at 字段建立索引，以支持高效的按用户查询和时间排序
8. THE Auth_System SHALL 利用 Cloudflare Workers 的 `request.cf` 对象和 `CF-Connecting-IP` 请求头获取登录/登出时的 IP 地址和地理位置信息
