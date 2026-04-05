@echo off
setlocal enabledelayedexpansion

echo ============================================
echo   Cloudflare Workers Deploy Script
echo ============================================
echo.

:: Step 1: Check if backup config exists
if not exist "wrangler.jsonc.bak" (
    echo [ERROR] wrangler.jsonc.bak not found.
    echo         Please create a backup with real config values first:
    echo         copy wrangler.jsonc wrangler.jsonc.bak
    echo         Then fill in the real database_id, KV id, GOOGLE_CLIENT_ID, etc.
    exit /b 1
)

:: Step 2: Restore production config
echo [1/4] Restoring production config from wrangler.jsonc.bak ...
copy /Y wrangler.jsonc.bak wrangler.jsonc >nul
if errorlevel 1 (
    echo [ERROR] Failed to restore production config.
    exit /b 1
)
echo       Done.
echo.

:: Step 3: Deploy to Cloudflare
echo [2/4] Deploying to Cloudflare Workers ...
echo.
call npx wrangler deploy
set DEPLOY_EXIT_CODE=!errorlevel!
echo.

:: Step 4: Restore desensitized config regardless of deploy result
echo [3/4] Restoring desensitized config from git ...
git checkout wrangler.jsonc >nul 2>&1
if errorlevel 1 (
    echo [WARN] git checkout failed. You may need to manually restore wrangler.jsonc.
) else (
    echo       Done.
)
echo.

:: Step 5: Report result
echo [4/4] Result:
if !DEPLOY_EXIT_CODE! equ 0 (
    echo       Deploy SUCCEEDED.
) else (
    echo       Deploy FAILED with exit code !DEPLOY_EXIT_CODE!.
    echo       Check the output above for details.
)

echo.
echo ============================================
endlocal
exit /b %DEPLOY_EXIT_CODE%
