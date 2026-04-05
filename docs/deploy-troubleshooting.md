# Cloudflare Python Workers 部署问题排查手册

本文档记录了在 Windows 环境下将 Python Workers (FastAPI) 部署到 Cloudflare 过程中遇到的所有问题及其解决方案。

---

## 问题 1：wrangler.jsonc 编码错误（GBK Codec Error）

### 现象

执行 `uv run pywrangler deploy` 时报错：

```
'gbk' codec can't decode byte 0x80 in position 918: illegal multibyte sequence
```

### 原因

`pywrangler` 内部使用 Python 的 `subprocess` 模块读取 `wrangler.jsonc` 文件。在中文 Windows 系统上，默认编码为 GBK，而 `wrangler.jsonc` 中包含中文注释（UTF-8 编码），导致解码失败。

### 解决方案

将 `wrangler.jsonc` 中的中文注释替换为英文注释，确保文件内容为纯 ASCII 字符：

```jsonc
// Before (会导致 GBK 解码失败)
// NOTE: GOOGLE_CLIENT_SECRET 应通过 `wrangler secret put` 设置为 Secrets

// After (纯 ASCII，兼容所有编码)
// NOTE: GOOGLE_CLIENT_SECRET should be set via `wrangler secret put` as Secrets
```

---

## 问题 2：pywrangler 无法找到 npx 命令

### 现象

`pywrangler deploy` 在包同步完成后报错：

```
Passing command to npx wrangler: npx --yes wrangler deploy
Command not found: npx. Is it installed and in PATH?
```

### 原因

`pywrangler` 使用 `shutil.which("npx")` 查找 `npx` 可执行文件。在 `uv run` 创建的虚拟环境子进程中，`PATH` 环境变量可能不包含 Node.js 的安装路径，导致 `shutil.which` 返回 `None`。

### 解决方案

将部署过程拆分为两步：

1. 使用 `pywrangler sync` 完成包安装（不依赖 npx）
2. 直接使用 `npx wrangler deploy` 完成部署（绕过 pywrangler 的 npx 查找逻辑）

```powershell
# 步骤 1：同步包
uv run pywrangler sync --force

# 步骤 2：直接部署（需手动修复 python_modules，见问题 3）
echo y | npx wrangler deploy
```

---

## 问题 3：pywrangler 在 Windows 上安装了原生 .pyd 而非 Pyodide .so

### 现象

部署到 Cloudflare 后，运行时报错：

```
ImportError: cannot import name 'BaseModel' from 'pydantic'
```

### 原因

`pywrangler sync` 在 Windows 上使用 `uv pip install --no-build --prefix ... --extra-index-url https://index.pyodide.org/...` 安装包。虽然指定了 Pyodide 索引作为额外源，但 `uv` 的 `unsafe-best-match` 策略会优先选择与本地 Python 解释器匹配的原生 Windows wheel（`.pyd` 文件），而非 Pyodide 兼容的 WebAssembly wheel（`.so` 文件）。

`pydantic_core` 是一个包含 Rust 编译的原生扩展的包。Windows 原生的 `_pydantic_core.cp312-win_amd64.pyd` 无法在 Cloudflare Workers 的 Pyodide (WebAssembly) 运行时中加载。

### 解决方案

手动下载 Pyodide 兼容的 `pydantic_core` wheel 并替换 `python_modules` 中的原生版本：

```powershell
# 1. 从 jsDelivr CDN 下载 Pyodide 专用 wheel
$whlUrl = "https://cdn.jsdelivr.net/pyodide/v0.28.3/full/pydantic_core-2.27.2-cp313-cp313-pyodide_2025_0_wasm32.whl"
Invoke-WebRequest -Uri $whlUrl -OutFile ".tmp_wheels\pydantic_core.whl" -UseBasicParsing

# 2. 重命名为 .zip 并解压（.whl 本质是 zip 格式）
Copy-Item ".tmp_wheels\pydantic_core.whl" ".tmp_wheels\pydantic_core.zip"
Expand-Archive -Path ".tmp_wheels\pydantic_core.zip" -DestinationPath ".tmp_wheels\extracted" -Force

# 3. 删除原生版本，替换为 Pyodide 版本
Remove-Item -Recurse -Force "python_modules\pydantic_core"
Copy-Item ".tmp_wheels\extracted\pydantic_core" "python_modules\pydantic_core" -Recurse
```

替换后验证：
```powershell
Get-ChildItem python_modules\pydantic_core\_pydantic_core*
# 期望输出: _pydantic_core.cpython-313-wasm32-emscripten.so
# 而非:     _pydantic_core.cp312-win_amd64.pyd
```

---

## 问题 4：Pyodide 内存快照序列化失败（Can't serialize top-level variable）

### 现象

部署时报错：

```
Uncaught Error: Can't serialize top-level variable.
Value: function () { [native code] }
Type: function
```

### 原因

Cloudflare Workers 在部署时会执行 Python 代码的顶层作用域，然后对 WebAssembly 线性内存进行快照（snapshot）。快照系统要求所有 JavaScript 对象引用必须可通过 `globalThis` 的属性访问链到达。

当 `pywrangler sync` 安装的纯 Python 包（如 `pydantic`、`fastapi`）版本与手动放置的 Pyodide `pydantic_core` `.so` 版本不完全匹配时，初始化过程中可能创建无法序列化的 JavaScript 函数引用。

### 解决方案

确保所有包版本一致。使用 `uv pip install` 配合 `--python-platform wasm32-pyodide2024` 安装纯 Python 包，然后仅手动替换 `pydantic_core`：

```powershell
# 安装纯 Python 包（指定 Pyodide 平台，排除 pydantic_core）
uv pip install --no-build `
  --target "python_modules" `
  --python-platform wasm32-pyodide2024 `
  --python-version 3.13 `
  "fastapi==0.135.3" "pydantic==2.10.6" "starlette==0.45.3" `
  anyio annotated-types typing-extensions typing-inspection annotated-doc idna `
  --extra-index-url "https://index.pyodide.org/0.28.3" `
  --index-strategy unsafe-best-match `
  --no-deps

# 然后手动添加 pydantic_core 的 Pyodide wheel（见问题 3）
```

---

## 问题 5：Python 版本与 Pyodide wheel 的 ABI 标签不匹配

### 现象

部署后运行时报错（pydantic_core 的 `.so` 无法加载），或 `uv pip install` 报错：

```
No solution found when resolving dependencies:
Because pydantic-core==2.27.2 has no usable wheels...
```

### 原因

Cloudflare Workers 的 Python 版本由 `compatibility_date` 和 `compatibility_flags` 共同决定：

| compatibility_date | compatibility_flags | Python 版本 | Pyodide 版本 |
|---|---|---|---|
| < 2025-09-29 | `python_workers` | 3.12 | 0.27.7 |
| >= 2025-09-29 | `python_workers` | 3.13 | 0.28.3 |

`uv` 的 `--python-platform` 参数仅支持 `wasm32-pyodide2024`，对应 Pyodide 0.27.7 的 `pyodide_2024_0` 平台标签。而 Pyodide 0.28.3 使用 `pyodide_2025_0` 平台标签，`uv` 尚未支持。

如果 `compatibility_date` 设置为 `2026-04-04`（>= 2025-09-29），运行时使用 Python 3.13，但 `uv` 只能解析 cp312 的 Pyodide wheel，导致 ABI 不匹配。

### 解决方案

使用 `uv` 安装纯 Python 包（不受 ABI 限制），手动下载 cp313 的 Pyodide wheel 用于 `pydantic_core`：

```powershell
# 纯 Python 包通过 uv 安装（py3-none-any wheel，无 ABI 限制）
uv pip install --no-build --target python_modules `
  --python-platform wasm32-pyodide2024 --python-version 3.13 `
  "fastapi==0.135.3" "pydantic==2.10.6" ... --no-deps

# pydantic_core 手动从 Pyodide CDN 下载 cp313 版本
# URL: https://cdn.jsdelivr.net/pyodide/v0.28.3/full/pydantic_core-2.27.2-cp313-cp313-pyodide_2025_0_wasm32.whl
```

### 版本对照表

| Pyodide 版本 | Python ABI | pydantic_core wheel 标签 | CDN 下载路径 |
|---|---|---|---|
| 0.27.7 | cp312 | `cp312-cp312-pyodide_2024_0_wasm32` | `cdn.jsdelivr.net/pyodide/v0.27.7/full/` |
| 0.28.3 | cp313 | `cp313-cp313-pyodide_2025_0_wasm32` | `cdn.jsdelivr.net/pyodide/v0.28.3/full/` |

---

## 问题 6：Worker 启动超出 CPU 时间限制

### 现象

部署时报错：

```
Python Worker startup exceeded CPU limit 1721<=1000 with snapshot baseline
```

### 原因

使用较旧的 `compatibility_date`（< 2025-09-29）会使运行时选择 Python 3.12 (Pyodide 0.27.7)，该版本缺少 Cloudflare 后续引入的内存快照优化（dedicated memory snapshots）。FastAPI + Pydantic 的模块导入开销较大，在没有快照优化的情况下超出了 Workers 免费套餐的 CPU 启动时间限制（1000ms）。

### 解决方案

使用 `compatibility_date >= 2025-09-29` 以启用 Python 3.13 运行时，该版本包含内存快照优化，可显著降低冷启动时间：

```jsonc
{
  "compatibility_date": "2026-04-04",
  "compatibility_flags": ["python_workers"]
}
```

---

## 问题 7：FastAPI 与 Starlette 版本不兼容

### 现象

部署后运行时报错：

```
TypeError: Router.__init__() got an unexpected keyword argument 'on_startup'
```

### 原因

`uv pip install` 在不指定版本约束时安装了最新的 `fastapi==0.116.1` 和 `starlette==1.0.0`。Starlette 1.0 移除了 `on_startup` / `on_shutdown` 参数（改用 `lifespan`），但 FastAPI 0.116.1 的内部代码仍然传递了这些已废弃的参数，导致运行时 `TypeError`。

### 解决方案

锁定兼容的版本组合：

```powershell
uv pip install --no-deps `
  "fastapi==0.135.3" `
  "pydantic==2.10.6" `
  "starlette==0.45.3"
```

FastAPI 0.135.3 依赖 `starlette>=0.40.0,<0.46.0`，与 `starlette==0.45.3` 兼容。

---

## 完整部署流程（推荐）

综合以上所有问题的解决方案，在 Windows 上部署 Cloudflare Python Workers 的完整流程如下：

```powershell
# 1. 确保 wrangler.jsonc 中无非 ASCII 字符（中文注释改为英文）

# 2. 安装纯 Python 依赖（指定 Pyodide 平台）
Remove-Item -Recurse -Force python_modules -ErrorAction SilentlyContinue
uv pip install --no-build `
  --target python_modules `
  --python-platform wasm32-pyodide2024 `
  --python-version 3.13 `
  "fastapi==0.135.3" "pydantic==2.10.6" "starlette==0.45.3" `
  anyio annotated-types typing-extensions typing-inspection annotated-doc idna `
  --extra-index-url "https://index.pyodide.org/0.28.3" `
  --index-strategy unsafe-best-match `
  --no-deps

# 3. 下载并安装 Pyodide 版 pydantic_core
$whlUrl = "https://cdn.jsdelivr.net/pyodide/v0.28.3/full/pydantic_core-2.27.2-cp313-cp313-pyodide_2025_0_wasm32.whl"
New-Item -ItemType Directory -Path .tmp_wheels -Force | Out-Null
Invoke-WebRequest -Uri $whlUrl -OutFile ".tmp_wheels\pydantic_core.whl" -UseBasicParsing
Copy-Item ".tmp_wheels\pydantic_core.whl" ".tmp_wheels\pydantic_core.zip"
Expand-Archive -Path ".tmp_wheels\pydantic_core.zip" -DestinationPath ".tmp_wheels\extracted" -Force
Copy-Item ".tmp_wheels\extracted\pydantic_core" "python_modules\pydantic_core" -Recurse -Force
Remove-Item -Recurse -Force .tmp_wheels

# 4. 部署
echo y | npx wrangler deploy
```

### wrangler.jsonc 关键配置

```jsonc
{
  "compatibility_date": "2026-04-04",
  "compatibility_flags": ["python_workers"],
  "main": "src/main.py"
}
```
