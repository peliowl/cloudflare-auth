# Wrangler 配置脱敏后的云端部署影响分析与解决方案

## 1. 背景

在团队协作与开源场景下，将 `wrangler.jsonc` 等配置文件中的敏感信息（数据库 ID、API 密钥、域名等）替换为占位符后提交至 Git 仓库，是保障信息安全的常规做法。然而，Cloudflare Workers 的部署流程（`npx wrangler deploy`）会直接读取本地 `wrangler.jsonc` 中的配置值并将其同步至云端运行时环境，因此需要明确哪些字段脱敏后会影响线上服务。

## 2. 配置分类与影响分析

### 2.1 脱敏后不影响线上的配置（Secrets 类）

| 配置项 | 存储位置 | 说明 |
|--------|---------|------|
| `JWT_SECRET` | Cloudflare Secrets 加密存储 | 通过 `wrangler secret put` 写入，不存在于 `wrangler.jsonc` 中 |
| `GOOGLE_CLIENT_SECRET` | Cloudflare Secrets 加密存储 | 同上 |

**原理：** Cloudflare Workers 的 Secrets 机制将敏感值存储在平台侧的加密存储中，Worker 在运行时通过环境变量读取。`wrangler.jsonc` 中的 `secrets.required` 字段仅用于部署前校验（确保 Secret 已设置），不包含实际值。

**同理：** `.dev.vars` 文件仅供本地开发（`wrangler dev`）使用，不会被上传至云端，且已被 `.gitignore` 排除。

### 2.2 脱敏后会影响线上的配置（Bindings & Vars 类）

| 字段路径 | 当前占位符 | 线上影响 |
|----------|-----------|---------|
| `d1_databases[0].database_id` | `<your-d1-database-id>` | Worker 无法绑定 D1 数据库实例，所有数据库读写操作抛出运行时异常 |
| `kv_namespaces[0].id` | `<your-kv-namespace-id>` | Worker 无法访问 KV 命名空间，Token 黑名单等依赖 KV 的功能完全失效 |
| `vars.GOOGLE_CLIENT_ID` | `<your-google-client-id>.apps.googleusercontent.com` | Google OAuth 2.0 授权请求携带无效的 `client_id`，登录流程无法发起 |
| `vars.OAUTH_REDIRECT_BASE_URL` | `https://<your-domain>` | OAuth 回调地址拼接错误，授权完成后无法正确重定向回应用 |

**原理：** 这些字段的值在执行 `wrangler deploy` 时被直接写入 Worker 的部署配置。占位符会被当作真实值使用，导致资源绑定失败或业务逻辑异常。

## 3. 解决方案

### 3.1 方案一：本地备份 + 部署脚本（推荐）

核心思路：仓库中保留脱敏版本，本地维护一份包含真实值的备份文件，通过脚本在部署时自动切换。

**步骤：**

1. 将当前包含真实值的配置备份为 `wrangler.jsonc.bak`（已被 `.gitignore` 中的 `*.bak` 规则忽略）：

```bash
copy wrangler.jsonc wrangler.jsonc.bak
```

2. 将 `wrangler.jsonc` 中的敏感值替换为占位符后提交至仓库。

3. 创建部署脚本 `deploy.bat`（Windows）：

```bat
@echo off
echo [1/3] Restoring production config...
copy /Y wrangler.jsonc.bak wrangler.jsonc

echo [2/3] Deploying to Cloudflare...
npx wrangler deploy

echo [3/3] Restoring desensitized config...
git checkout wrangler.jsonc

echo Done.
```

4. 将 `deploy.bat` 加入 `.gitignore`（可选，视团队规范而定）。

**优点：** 操作简单，无需改动项目结构；备份文件不会被提交。

**缺点：** 依赖本地备份文件的存在，新成员需手动创建。

### 3.2 方案二：Wrangler 多环境配置（env）

利用 Wrangler 原生的 `env` 字段为不同环境定义独立配置：

```jsonc
{
  // 顶层为脱敏的默认配置（安全提交）
  "d1_databases": [
    {
      "binding": "DB",
      "database_name": "cloudflare-auth-db",
      "database_id": "<your-d1-database-id>"
    }
  ],

  // 生产环境覆盖
  "env": {
    "production": {
      "d1_databases": [
        {
          "binding": "DB",
          "database_name": "cloudflare-auth-db",
          "database_id": "真实的D1数据库ID"
        }
      ],
      "kv_namespaces": [
        {
          "binding": "TOKEN_BLACKLIST",
          "id": "真实的KV命名空间ID"
        }
      ],
      "vars": {
        "GOOGLE_CLIENT_ID": "真实的Google客户端ID.apps.googleusercontent.com",
        "OAUTH_REDIRECT_BASE_URL": "https://真实域名"
      }
    }
  }
}
```

部署时指定环境：

```bash
npx wrangler deploy --env production
```

**注意：** 此方案中 `env.production` 的真实值仍存在于文件内，若提交至公开仓库仍会暴露。适用于私有仓库或配合 `.gitignore` 单独管理环境配置文件的场景。

### 3.3 方案三：CI/CD 环境变量注入

在 CI/CD 流水线（如 GitHub Actions）中，将敏感配置存储为 Repository Secrets，部署前通过脚本动态替换占位符：

```yaml
# .github/workflows/deploy.yml 示例片段
- name: Inject production config
  run: |
    sed -i 's/<your-d1-database-id>/${{ secrets.D1_DATABASE_ID }}/g' wrangler.jsonc
    sed -i 's/<your-kv-namespace-id>/${{ secrets.KV_NAMESPACE_ID }}/g' wrangler.jsonc
    sed -i 's/<your-google-client-id>/${{ secrets.GOOGLE_CLIENT_ID }}/g' wrangler.jsonc
    sed -i 's/<your-domain>/${{ secrets.DOMAIN }}/g' wrangler.jsonc

- name: Deploy
  run: npx wrangler deploy
  env:
    CLOUDFLARE_API_TOKEN: ${{ secrets.CF_API_TOKEN }}
```

**优点：** 敏感值完全不存在于代码仓库中，安全性最高。

**缺点：** 需要配置 CI/CD 流水线，本地手动部署时仍需方案一辅助。

## 4. 总结

| 配置类型 | 脱敏影响 | 处理方式 |
|----------|---------|---------|
| Secrets（`JWT_SECRET`、`GOOGLE_CLIENT_SECRET`） | 无影响 | 通过 `wrangler secret put` 管理，与配置文件无关 |
| Bindings ID（`database_id`、KV `id`） | 线上不可用 | 部署前还原真实值，或通过 CI/CD 注入 |
| 环境变量（`GOOGLE_CLIENT_ID`、`OAUTH_REDIRECT_BASE_URL`） | 线上不可用 | 同上 |

**推荐实践：** 日常开发使用方案一（本地备份 + 部署脚本），团队协作或自动化部署场景使用方案三（CI/CD 注入）。两者可结合使用，互为补充。
