# 邮箱验证码邮件模板方案

## 概述

本文档描述 Cloudflare Auth 项目中邮箱验证码邮件的模板化方案。该方案将邮件内容从后端代码中解耦，迁移至 Resend 平台的模板系统进行管理，实现邮件内容的动态维护与热更新，消除硬编码依赖。

---

## 1. 方案背景

### 1.1 原有实现

邮箱验证码邮件的 HTML 内容硬编码在 `src/auth/email_verification_service.py` 的 `_build_email_html()` 方法中。每次修改邮件样式或文案均需变更后端代码并重新部署 Worker。

### 1.2 改进目标

| 目标 | 说明 |
|------|------|
| 内容与代码解耦 | 邮件模板由 Resend 平台托管，后端仅传递模板 ID 和变量 |
| 热更新 | 在 Resend Dashboard 中修改并发布模板后立即生效，无需重新部署 |
| 向后兼容 | 未配置模板 ID 时自动回退到内置 HTML 模板，确保零停机迁移 |

---

## 2. 架构设计

### 2.1 发送流程

```
发送验证码请求
    │
    ├─ 人机验证 (Turnstile)
    ├─ 邮箱注册检查 (D1)
    ├─ 冷却期检查 (KV)
    ├─ 生成 6 位验证码
    ├─ 存储验证码到 KV (TTL=300s)
    │
    ├─ [判断] RESEND_TEMPLATE_ID 是否已配置？
    │   ├─ 是 → 调用 Resend Template API
    │   │       POST https://api.resend.com/emails
    │   │       Body: { from, to, subject, template: { id, variables } }
    │   │
    │   └─ 否 → 使用内置 HTML 模板（回退模式）
    │           POST https://api.resend.com/emails
    │           Body: { from, to, subject, html }
    │
    └─ 设置冷却标记 (KV, TTL=60s)
```

### 2.2 关键决策

- 模板 ID 通过环境变量 `RESEND_TEMPLATE_ID` 注入，属于非敏感公开配置，配置在 `wrangler.jsonc` 的 `vars` 中
- 模板变量仅包含一个字段 `verification_code`，对应 6 位数字验证码
- `subject` 字段始终由后端传入（`"您的验证码"`），不依赖模板内置主题

---

## 3. 模板文件

### 3.1 文件位置

```
template/
└── verification-code-email.html    # 邮箱验证码邮件模板源文件
```

### 3.2 模板变量

| 变量名 | 类型 | 说明 |
|--------|------|------|
| `verification_code` | string | 6 位数字验证码，如 `"384729"` |

在模板 HTML 中使用 `{{verification_code}}` 占位符标记变量位置。

### 3.3 设计风格

模板遵循项目统一的极简现代化 UI 风格：

- 主色调：`#0f172a`（slate-900）
- 背景色：`#fafafa`（页面）/ `#ffffff`（卡片）
- 辅助色：`#64748b`（副标题）、`#94a3b8`（提示文字）、`#cbd5e1`（安全提醒）
- 圆角：`16px`（卡片）、`12px`（验证码区域）
- 字体：系统字体栈（`-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto`）
- 布局：居中单列卡片，宽度 420px，大量留白

### 3.4 模板结构

```
┌─────────────────────────────┐
│       Cloudflare Auth       │  ← 品牌标识
│                             │
│      您的邮箱验证码          │  ← 标题
│                             │
│  ┌─────────────────────┐    │
│  │     384729          │    │  ← 验证码（大号加粗，字间距 8px）
│  └─────────────────────┘    │
│                             │
│   验证码有效期为 5 分钟      │  ← 有效期提示
│                             │
│  ─────────────────────────  │  ← 分隔线
│  如果您没有请求此验证码，    │  ← 安全提醒
│  请忽略此邮件。              │
└─────────────────────────────┘
```

---

## 4. Resend 平台配置指南

### 4.1 创建模板

1. 登录 [Resend Dashboard](https://resend.com/templates)
2. 点击 **Create template**
3. 将 `template/verification-code-email.html` 的内容粘贴到编辑器中
4. 添加变量 `verification_code`（类型：string，无需设置 fallback）
5. 发送测试邮件确认渲染效果
6. 点击 **Publish** 发布模板
7. 复制模板 ID（格式如 `tm_xxxxxxxx`）

### 4.2 配置环境变量

将模板 ID 配置到项目中：

**本地开发**（`.dev.vars`）：

```
RESEND_TEMPLATE_ID="tm_xxxxxxxx"
```

**生产环境**（`wrangler.jsonc`）：

```jsonc
"vars": {
    "RESEND_TEMPLATE_ID": "tm_xxxxxxxx"
}
```

### 4.3 更新模板

1. 在 Resend Dashboard 中编辑模板内容
2. 修改完成后点击 **Publish** 发布新版本
3. 邮件内容立即生效，无需重新部署 Worker

> Resend 支持模板版本历史，未发布的修改保存为草稿，不影响线上邮件发送。

---

## 5. 后端实现细节

### 5.1 配置常量

文件：`src/core/config.py`

```python
RESEND_TEMPLATE_VARIABLE_NAME = "verification_code"
```

### 5.2 模板 ID 获取

文件：`src/auth/email_verification_service.py`

`_get_template_id()` 方法从 `env.RESEND_TEMPLATE_ID` 读取模板 ID。当环境变量未设置、为空字符串或为 JavaScript 的 `undefined`/`null` 时返回 `None`，触发回退逻辑。

### 5.3 模板发送

`_send_email_with_template()` 方法构造符合 Resend Template API 规范的请求体：

```json
{
    "from": "noreply@your-domain.com",
    "to": ["user@example.com"],
    "subject": "您的验证码",
    "template": {
        "id": "tm_xxxxxxxx",
        "variables": {
            "verification_code": "384729"
        }
    }
}
```

### 5.4 回退机制

当 `RESEND_TEMPLATE_ID` 未配置时，系统自动使用 `_build_email_html()` 方法生成内置 HTML 并通过 `html` 字段发送，行为与改造前完全一致。

---

## 6. 文件变更清单

| 文件 | 变更说明 |
|------|---------|
| `template/verification-code-email.html` | 新增：邮件模板源文件，供开发者维护到 Resend 平台 |
| `src/core/config.py` | 新增 `RESEND_TEMPLATE_VARIABLE_NAME` 常量 |
| `src/auth/email_verification_service.py` | 新增 `_get_template_id()`、`_send_email_with_template()` 方法；修改 `send_verification_code()` 优先使用模板发送 |
| `wrangler.jsonc` | `vars` 中新增 `RESEND_TEMPLATE_ID` 配置项 |
| `.dev.vars.example` | 新增 `RESEND_TEMPLATE_ID` 示例 |

---

## 7. 注意事项

1. **模板必须处于已发布状态**：Resend 仅允许使用已发布的模板发送邮件，草稿状态的模板会导致 API 返回验证错误
2. **变量名一致性**：模板中的变量名 `verification_code` 必须与后端代码中的 `RESEND_TEMPLATE_VARIABLE_NAME` 保持一致
3. **零停机迁移**：可先部署代码变更（不配置 `RESEND_TEMPLATE_ID`），系统将继续使用内置 HTML；待 Resend 模板创建并发布后，再配置环境变量即可切换
4. **邮件主题**：`subject` 字段由后端代码控制，不受模板影响，确保主题一致性
