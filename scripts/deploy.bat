@echo off
setlocal enabledelayedexpansion

echo ============================================
echo   Cloudflare Workers Deploy Script
echo ============================================
echo.

:: Step 1: Check if wrangler.jsonc exists with real config
if not exist "wrangler.jsonc" (
    echo [ERROR] wrangler.jsonc not found.
    echo         Please create it from the template:
    echo         copy wrangler.jsonc.example wrangler.jsonc
    echo         Then fill in the real database_id, KV id, GOOGLE_CLIENT_ID, etc.
    exit /b 1
)

:: Step 2: Verify it contains real values (quick sanity check)
findstr /C:"<your-" wrangler.jsonc >nul 2>&1
if not errorlevel 1 (
    echo [ERROR] wrangler.jsonc still contains placeholder values.
    echo         Please replace all ^<your-...^> placeholders with real values.
    exit /b 1
)

:: Step 3: Deploy to Cloudflare
echo [1/2] Deploying to Cloudflare Workers ...
echo.
call npx wrangler deploy
set DEPLOY_EXIT_CODE=!errorlevel!
echo.

:: Step 4: Report result
echo [2/2] Result:
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
