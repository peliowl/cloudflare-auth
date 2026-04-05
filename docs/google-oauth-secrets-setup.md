# Google OAuth 密钥安全配置指南

## 概述

本项目使用 Cloudflare Workers Secrets 管理敏感凭据（JWT 密钥、OAuth client secret 等），确保这些值不会出现在代码仓库或 `wrangler.jsonc` 配置文件中。

## 涉及的 Secrets

| Secret 名称 | 用途 | 获取方式 |
|---|---|---|
| `JWT_SECRET` | JWT 令牌签名密钥 | 自行生成强随机字符串 |
| `GOOGLE_CLIENT_SECRET` | Google OAuth 2.0 客户端密钥 | Google Cloud Console |

## 生产环境配置

使用 `wrangler secret put` 将 secret 加密存储到 Cloudflare：

```bash
# 设置 JWT 签名密钥（建议使用 openssl 生成）
npx wrangler secret put JWT_SECRET
# 输入值，例如: openssl rand -hex 32 生成的随机字符串

# 设置 Google OAuth client secret
npx wrangler secret put GOOGLE_CLIENT_SECRET
# 输入从 Google Cloud Console 获取的 client_secret
```

设置完成后，secret 值会被加密存储，在 Cloudflare Dashboard 和 Wrangler 中均不可见。Worker 代码通过 `env.GOOGLE_CLIENT_SECRET` 等方式访问。

## 本地开发配置

本地开发时，secret 通过 `.dev.vars` 文件提供（该文件已被 `.gitignore` 忽略）：

1. 复制示例文件：
   ```bash
   cp .dev.vars.example .dev.vars
   ```

2. 编辑 `.dev.vars`，填入实际值：
   ```
   JWT_SECRET="your-strong-random-secret"
   GOOGLE_CLIENT_SECRET="your-google-client-secret"
   ```

3. 启动本地开发服务器，secret 会自动加载：
   ```bash
   npx wrangler dev
   ```

## 获取 Google OAuth Client Secret

1. 访问 [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. 选择对应项目，找到已创建的 OAuth 2.0 客户端 ID
3. 点击编辑，复制 **客户端密钥 (Client Secret)**
4. 确保已配置正确的授权重定向 URI：`https://auth.peliowl.asia/auth/oauth/callback/google`

## wrangler.jsonc 中的 secrets 声明

`wrangler.jsonc` 中的 `secrets.required` 字段声明了 Worker 所需的 secret 名称。这不会存储实际值，仅用于：

- **部署验证**：`wrangler deploy` 时检查所有必需 secret 是否已设置，未设置则部署失败
- **类型生成**：`wrangler types` 时生成正确的类型定义
- **本地开发验证**：`wrangler dev` 时检查 `.dev.vars` 中是否包含所需 secret

## 安全注意事项

- `.dev.vars` 已在 `.gitignore` 中，不会被提交到代码仓库
- 生产环境的 secret 通过 Cloudflare 加密存储，仅 Worker 运行时可访问
- `GOOGLE_CLIENT_ID` 等非敏感配置保留在 `wrangler.jsonc` 的 `vars` 中
- 切勿将 client secret 硬编码在源代码或配置文件中
