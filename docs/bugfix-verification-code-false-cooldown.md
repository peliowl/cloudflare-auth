# BUG 修复报告：验证码发送接口误报冷却中（429）

## 1. 问题描述

### 1.1 现象

用户在注册页面点击「发送验证码」，调用 `POST /auth/send-verification-code` 接口时，服务端返回：

```json
{ "detail": "验证码已发送，请稍后再试" }
```

HTTP 状态码为 `429 Too Many Requests`。

但登录 Cloudflare Dashboard 检查 KV 存储后发现：**不存在对应的 `email_cooldown:{email}` 键**，也不存在 `email_code:{email}` 键。即冷却期与验证码均未实际写入，接口却拒绝了请求。

### 1.2 影响范围

- 注册流程完全阻断：用户无法获取邮箱验证码，无法完成注册。
- 该问题在首次发送验证码时即可复现，并非仅在重复发送时出现。

---

## 2. 技术背景

### 2.1 运行时架构

本项目基于 **Cloudflare Workers + Python (Pyodide)** 构建。Python 代码通过 Pyodide 的 **Foreign Function Interface (FFI)** 调用 JavaScript 运行时 API，包括 KV Namespace 的 `get()` / `put()` 方法。

### 2.2 Pyodide FFI 中的 `null` 语义

在 JavaScript 中，`KVNamespace.get(key)` 对不存在的键返回 `null`。该值经 Pyodide FFI 传递到 Python 侧时，**不会**被转换为 Python 的 `None`，而是变为 `pyodide.ffi.jsnull` —— 一个 `pyodide.ffi.JsNull` 类型的单例对象。

其关键特性如下：

| 表达式 | 结果 | 说明 |
|---|---|---|
| `jsnull is None` | `False` | `jsnull` 不是 Python `None` |
| `bool(jsnull)` | `False` | `jsnull` 是 falsy 的 |
| `str(jsnull)` | 非 `"null"` | 其字符串表示并非字面量 `"null"` |

> 参考：项目内 `src/core/jwt_utils.py` 中已有注释说明此行为：
> *"KV.get() returns JS null for missing keys. In Pyodide, JS null becomes pyodide.ffi.jsnull (not Python None)."*

---

## 3. 根因分析

### 3.1 缺陷代码

文件：`src/auth/email_verification_service.py`，`send_verification_code` 方法中的冷却检查逻辑：

```python
# 旧代码（存在缺陷）
cooldown = await self.kv.get(f"email_cooldown:{email}")
if cooldown is not None and str(cooldown) not in ("undefined", "null", ""):
    raise HTTPException(status_code=429, detail="验证码已发送，请稍后再试")
```

### 3.2 执行路径推演

当 `email_cooldown:{email}` 键不存在时：

1. `self.kv.get(...)` 返回 JavaScript `null`，Python 侧接收到 `pyodide.ffi.jsnull`。
2. `cooldown is not None` → **`True`**（`jsnull` 不是 Python `None`）。
3. `str(cooldown)` → 产生 `jsnull` 的默认字符串表示（如 `"jsnull"` 或对象 repr），**不在** `("undefined", "null", "")` 之中。
4. 整个条件表达式求值为 `True`，抛出 `HTTPException(429)`。

**结论**：冷却检查对 KV 缺失键的返回值处理不当，导致任何请求都被误判为"冷却中"。

### 3.3 对比项目内正确实现

| 文件 | 检查方式 | 是否正确 |
|---|---|---|
| `src/core/jwt_utils.py` | `if result is None: ... return bool(result)` | ✅ 利用 falsy 特性 |
| `src/auth/oauth_service.py` | `if state_data_raw is None or not state_data_raw:` | ✅ `not jsnull` 为 `True` |
| `src/auth/email_verification_service.py` | `str(cooldown) not in ("undefined", "null", "")` | ❌ 字符串比较不可靠 |

---

## 4. 修复方案

### 4.1 核心思路

放弃基于 `str()` 的字符串比较，改用 **truthiness 检查**。`pyodide.ffi.jsnull` 是 falsy 的，与 `None` 一样可被 `not` 或 `bool()` 正确识别。

### 4.2 代码变更

文件：`src/auth/email_verification_service.py`

**变更一：冷却检查（`send_verification_code` 方法）**

```python
# 修复后
cooldown = await self.kv.get(f"email_cooldown:{email}")
if cooldown is not None and cooldown:
    raise HTTPException(status_code=429, detail="验证码已发送，请稍后再试")
```

- `cooldown is not None`：排除 Python `None`（理论上不会出现，作为防御性检查保留）。
- `and cooldown`：利用 truthiness 排除 `jsnull`（falsy）。仅当 KV 返回真实的字符串值（truthy）时才触发冷却拦截。

**变更二：验证码校验（`verify_code` 方法）**

```python
# 修复后
stored = await self.kv.get(f"email_code:{email}")
if stored is None or not stored:
    return False
return str(stored) == code
```

- 同理，将 `str(stored) in ("undefined", "null", "")` 替换为 `not stored`，统一处理 `None` 和 `jsnull`。

### 4.3 修复后执行路径

当 `email_cooldown:{email}` 键不存在时：

1. `self.kv.get(...)` 返回 `jsnull`。
2. `cooldown is not None` → `True`。
3. `cooldown` → `jsnull` 是 falsy → `False`。
4. 条件短路，**不抛出异常**，流程继续执行验证码生成与发送。

---

## 5. 关联风险提示

在审查过程中发现，项目内其他文件的 KV `put()` 调用使用了 **`expiration_ttl`（snake_case）** 作为 TTL 参数名：

```python
# src/auth/oauth_service.py
await self.kv.put(f"oauth_state:{state}", json.dumps(kv_data), expiration_ttl=OAUTH_STATE_TTL)

# src/core/jwt_utils.py
await kv.put(f"blacklist:{jti}", "1", expiration_ttl=ttl_seconds)
```

而 JavaScript KV API 的 `put(key, value, options)` 中，options 对象的属性名为 **`expirationTtl`（camelCase）**。根据 [Pyodide FFI 文档](https://pyodide.org/en/stable/usage/type-conversions.html)，Python kwargs 会被原样转换为 JavaScript 对象属性（不做 snake_case → camelCase 转换）。因此 `expiration_ttl` 会生成 `{expiration_ttl: 600}`，该属性会被 JavaScript KV API **静默忽略**，导致键永不过期。

> 本次修复未涉及上述文件，建议后续排查并统一为 `expirationTtl`。

---

## 6. 验证方法

1. 清除 KV 中目标邮箱的所有相关键（`email_cooldown:*`、`email_code:*`）。
2. 在注册页面输入邮箱，点击「发送验证码」。
3. 预期结果：接口返回 `200`，邮箱收到验证码。
4. 60 秒内再次点击：接口返回 `429`，提示冷却中（预期行为）。
5. 60 秒后再次点击：接口返回 `200`，可正常重新发送。

---

## 7. 总结

| 项目 | 内容 |
|---|---|
| 根因 | Pyodide FFI 将 JS `null` 映射为 `jsnull`（非 Python `None`），`str()` 比较无法正确识别 |
| 修复策略 | 使用 truthiness 检查替代字符串比较，与项目内已有正确实现保持一致 |
| 影响文件 | `src/auth/email_verification_service.py` |
| 变更方法 | `send_verification_code`、`verify_code` |
