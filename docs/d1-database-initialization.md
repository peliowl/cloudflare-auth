# Cloudflare D1 数据库初始化指南

## 问题描述

### 现象

部署 Worker 到 Cloudflare 后，访问 `/auth/register` 接口（POST）时返回以下错误：

```json
{
  "level": "error",
  "message": "pyodide.ffi.JsException: Error: D1_ERROR: no such table: users: SQLITE_ERROR"
}
```

### 根因分析

Cloudflare D1 是一个 serverless SQLite 数据库。在 `wrangler.jsonc` 中配置 D1 binding 仅声明了 Worker 与数据库的绑定关系，并不会自动创建表结构。D1 数据库创建后默认为空，需要手动执行 DDL 语句初始化 schema。

与传统数据库部署流程不同，D1 没有内置的 migration 框架。开发者需要通过 `wrangler d1 execute` 命令手动执行 SQL 来管理 schema。

---

## 解决方案

### 1. 创建 Migration 文件

在项目根目录创建 `migrations/0001_init.sql`，定义所有需要的表结构：

```sql
-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT,
    role TEXT NOT NULL DEFAULT 'user',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Create oauth_accounts table
CREATE TABLE IF NOT EXISTS oauth_accounts (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    provider_user_id TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(provider, provider_user_id)
);
```

使用 `CREATE TABLE IF NOT EXISTS` 确保重复执行不会报错。

### 2. 在远程 D1 数据库上执行 Migration

#### 方式一：通过 `--file` 参数（推荐）

```powershell
npx wrangler d1 execute cloudflare-auth-db --remote --file=migrations/0001_init.sql
```

> 注意：`--file` 路径相对于 wrangler 的工作目录（通常是项目根目录）。如果终端当前目录不在项目根目录，需要先切换或使用绝对路径。

#### 方式二：通过 `--command` 参数内联 SQL

当 `--file` 因路径问题无法正常工作时，可以直接内联 SQL：

```powershell
npx wrangler d1 execute cloudflare-auth-db --remote --command="CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, email TEXT UNIQUE NOT NULL, password_hash TEXT, role TEXT NOT NULL DEFAULT 'user', created_at DATETIME DEFAULT CURRENT_TIMESTAMP);"
```

```powershell
npx wrangler d1 execute cloudflare-auth-db --remote --command="CREATE TABLE IF NOT EXISTS oauth_accounts (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, provider TEXT NOT NULL, provider_user_id TEXT NOT NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users(id), UNIQUE(provider, provider_user_id));"
```

> `--command` 每次只能执行一条 SQL 语句，多张表需要分多次执行。

### 3. 验证表是否创建成功

```powershell
npx wrangler d1 execute cloudflare-auth-db --remote --command="SELECT name FROM sqlite_master WHERE type='table';"
```

期望输出应包含 `users` 和 `oauth_accounts`。

---

## 踩坑记录：`--file` 路径解析问题（Windows）

### 现象

在 Windows 上执行 `--file` 参数时，wrangler 报错：

```
X [ERROR] Unable to read SQL text file "migrations/0001_init.sql". Please check the file path and try again.
```

### 原因

终端的工作目录（`cwd`）与项目根目录不一致。例如终端停留在 `src/` 子目录下，而 `--file` 的相对路径是基于终端 `cwd` 解析的，不是基于 `wrangler.jsonc` 所在目录。

### 解决方案

- 确保终端 `cwd` 在项目根目录下再执行命令
- 或使用 `--command` 参数内联 SQL 绕过文件路径问题
- 或使用绝对路径：`--file=D:\Working\Python\cloudflare-auth\migrations\0001_init.sql`

---

## 本地开发 vs 远程数据库

| 参数 | 目标数据库 | 用途 |
|------|-----------|------|
| `--remote` | Cloudflare 云端 D1 | 生产/预发布环境 |
| `--local`（默认） | 本地 `.wrangler/state/` 下的 SQLite | 本地开发 |

本地开发时 `npx wrangler dev` 会自动使用本地 D1 数据库，同样需要执行 migration：

```powershell
npx wrangler d1 execute cloudflare-auth-db --local --file=migrations/0001_init.sql
```

---

## 最佳实践

1. 将所有 DDL 语句维护在 `migrations/` 目录下，按序号命名（`0001_init.sql`、`0002_add_index.sql` 等）
2. 在 `README.md` 或部署文档中注明：部署后需执行 migration 初始化数据库
3. 使用 `CREATE TABLE IF NOT EXISTS` 保证幂等性
4. 每次新增表或修改 schema 时，创建新的 migration 文件，不要修改已执行过的旧文件
