# Windows 上运行 Cloudflare Python Workers (FastAPI) 解决方案

## 问题背景

在 Windows 上使用 `uv run pywrangler dev` 启动 Cloudflare Python Worker（FastAPI）时，会遇到以下错误：

```
error: Querying Python at `...\pyodide-3.13.2-emscripten-wasm32-musl\python.exe` failed
ModuleNotFoundError: No module named 'python'
```

根本原因：`pywrangler` 内部调用 `uv venv` 创建 Pyodide 虚拟环境时，`uv` 尝试查询 Pyodide 的 wasm `python.exe`（实际是一个 Node.js 脚本），但该解释器无法像普通 CPython 一样被 `uv` 查询，导致虚拟环境创建失败。

Cloudflare 官方 changelog 提到 Windows 支持需要 `workers-py >= 1.72.0`，但截至目前 PyPI 上最新版本为 `1.9.2`，该修复尚未发布。

## 前置条件

- Node.js + npm
- uv（Python 包管理器）
- wrangler >= 4.64.0（`npm install wrangler`）
- workers-py（`uv add --dev workers-py workers-runtime-sdk`）

## 解决步骤

### 1. 代码结构

`src/main.py` 必须使用 `WorkerEntrypoint` 类 + `asgi` 模块桥接 FastAPI：

```python
from workers import WorkerEntrypoint
from fastapi import FastAPI
from pydantic import BaseModel
import asgi


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        return await asgi.fetch(app, request, self.env)


app = FastAPI()


class UserQuery(BaseModel):
    name: str


@app.get("/")
async def root():
    return {"message": "Hello from Cloudflare Workers (Python)!"}


@app.post("/greet")
async def greet(query: UserQuery):
    return {"success": True, "payload": f"Hi {query.name}"}
```

### 2. 版本约束

`pyproject.toml` 中 pydantic 必须锁定到与 Pyodide 索引中 `pydantic-core` 匹配的版本：

```toml
[project]
dependencies = [
    "fastapi",
    "pydantic==2.10.6",
]
```

Pyodide 0.28.3 索引中 `pydantic-core` 最新版为 `2.27.2`，对应 `pydantic==2.10.4~2.10.6`。

### 3. Monkey-patch pywrangler（绕过 uv venv 失败）

编辑 `.venv/Lib/site-packages/pywrangler/sync.py`，修改 `create_pyodide_venv` 函数：

```python
def create_pyodide_venv() -> None:
    pyodide_venv_path = get_pyodide_venv_path()
    if pyodide_venv_path.is_dir():
        logger.debug(f"Pyodide virtual environment at {pyodide_venv_path} already exists.")
        return

    check_uv_version()
    logger.debug(f"Creating Pyodide virtual environment at {pyodide_venv_path}...")
    pyodide_venv_path.parent.mkdir(parents=True, exist_ok=True)
    interp_name = get_uv_pyodide_interp_name()
    run_command(["uv", "python", "install", interp_name])

    if os.name == "nt":
        # Windows workaround: 手动创建 venv 目录结构
        import subprocess
        result = subprocess.run(
            ["uv", "python", "find", interp_name],
            capture_output=True, text=True, check=False,
        )
        home_dir = Path(result.stdout.strip()).parent if result.returncode == 0 else ""
        pyv = get_python_version()

        site_packages = pyodide_venv_path / "Lib" / "site-packages"
        site_packages.mkdir(parents=True, exist_ok=True)
        scripts_dir = pyodide_venv_path / "Scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)

        if home_dir:
            src_exe = Path(home_dir) / "python.exe"
            if src_exe.exists():
                shutil.copy2(str(src_exe), str(scripts_dir / "python.exe"))

        cfg = pyodide_venv_path / "pyvenv.cfg"
        cfg.write_text(
            f"home = {home_dir}\n"
            f"include-system-site-packages = false\n"
            f"implementation = cpython\n"
            f"version_info = {pyv}\n"
        )
    else:
        run_command(["uv", "venv", str(pyodide_venv_path), "--python", interp_name])
```

同样修改 `_install_requirements_to_vendor` 函数，在 Windows 上使用 `--prefix` 替代 `VIRTUAL_ENV`：

```python
# 在 with temp_requirements_file(requirements) as requirements_file: 内部
if os.name == "nt":
    result = run_command(
        ["uv", "pip", "install", "--no-build", "--prefix",
         str(get_pyodide_venv_path()), "-r", requirements_file,
         "--extra-index-url", get_pyodide_index(),
         "--index-strategy", "unsafe-best-match"],
        capture_output=True, check=False,
    )
    # ... 后续 copytree 逻辑同原版
```

修改 `_get_vendor_package_versions` 函数，在 Windows 上去掉 `VIRTUAL_ENV`：

```python
if os.name == "nt":
    result = run_command(
        ["uv", "pip", "freeze", "--path", str(get_vendor_modules_path())],
        capture_output=True, check=False,
    )
else:
    # 原版逻辑
```

### 4. 运行 pywrangler sync

```powershell
$env:PATH = "$env:USERPROFILE\.local\bin;$env:PATH"
uv run pywrangler sync --force
```

### 5. 替换 pydantic-core 的 Windows 原生 wheel 为 Pyodide wasm wheel

`pywrangler sync` 的 `--prefix` 模式会安装 Windows 原生的 `pydantic-core`（`.pyd` 文件），Pyodide 运行时无法加载。需要手动替换为 pyodide wasm wheel。

从 jsDelivr CDN 下载 pyodide 专用 wheel：

```powershell
# 下载 pyodide wasm wheel
$url = "https://cdn.jsdelivr.net/pyodide/v0.28.3/full/pydantic_core-2.27.2-cp313-cp313-pyodide_2025_0_wasm32.whl"
Invoke-WebRequest -Uri $url -OutFile "pydantic_core_pyodide.whl" -UseBasicParsing

# 删除 Windows 原生版本
Remove-Item -Recurse -Force python_modules\pydantic_core

# 解压 pyodide wheel 中的 pydantic_core 目录
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead("pydantic_core_pyodide.whl")
foreach ($entry in $zip.Entries) {
    if ($entry.FullName.StartsWith("pydantic_core/")) {
        $destPath = Join-Path "python_modules" $entry.FullName
        $destDir = Split-Path $destPath -Parent
        if (-not (Test-Path $destDir)) {
            New-Item -ItemType Directory -Path $destDir -Force | Out-Null
        }
        if (-not $entry.FullName.EndsWith("/")) {
            [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $destPath, $true)
        }
    }
}
$zip.Dispose()
Remove-Item "pydantic_core_pyodide.whl"
```

替换后验证：

```powershell
Get-ChildItem python_modules\pydantic_core\_pydantic_core* | Select-Object Name
# 应输出: _pydantic_core.cpython-313-wasm32-emscripten.so
```

### 6. 启动开发服务器

```powershell
npx wrangler dev
```

服务器启动后访问 `http://127.0.0.1:8787`。

## Pyodide 版本对照表

| compatibility_date | Pyodide 版本 | Python 版本 | pydantic-core (pyodide) | pydantic (兼容) |
|---|---|---|---|---|
| 2026-04-04 | 0.28.3 | 3.13 | 2.27.2 | 2.10.4~2.10.6 |

Pyodide 索引地址：`https://index.pyodide.org/{pyodide_version}/`

jsDelivr CDN 镜像：`https://cdn.jsdelivr.net/pyodide/v{pyodide_version}/full/`

## 注意事项

- `python_modules/` 目录不能放在 `src/`（module root）下，必须放在项目根目录
- 每次 `uv sync` 或 `pywrangler sync` 后都需要重新执行步骤 5 替换 pydantic-core
- 部署时使用 `uv run pywrangler deploy`，同样需要确保 `python_modules` 中的 pydantic-core 是 pyodide wasm 版本
- 当 Cloudflare 发布 `workers-py >= 1.72.0` 后，以上 workaround 将不再需要
