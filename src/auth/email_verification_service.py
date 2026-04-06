import json
import random

from fastapi import HTTPException

from core.config import (
    EMAIL_CODE_TTL,
    EMAIL_CODE_COOLDOWN,
    RESEND_API_URL,
    TURNSTILE_SITEVERIFY_URL,
    RESEND_TEMPLATE_VARIABLE_NAME,
)


class EmailVerificationService:
    def __init__(self, kv, env):
        self.kv = kv
        self.env = env

    def _generate_code(self) -> str:
        return str(random.SystemRandom().randint(100000, 999999))

    async def verify_turnstile(self, token: str, remote_ip: str | None) -> bool:
        """Verify Turnstile token. Returns True if valid, False if invalid.
        Raises HTTPException(502) if the Siteverify API itself is unreachable."""
        from js import fetch, Headers

        headers = Headers.new()
        headers.set("Content-Type", "application/json")

        body = {
            "secret": str(self.env.TURNSTILE_SECRET_KEY),
            "response": token,
        }
        if remote_ip:
            body["remoteip"] = remote_ip

        try:
            response = await fetch(
                TURNSTILE_SITEVERIFY_URL,
                method="POST",
                headers=headers,
                body=json.dumps(body),
            )
        except Exception:
            raise HTTPException(status_code=502, detail="人机验证服务暂时不可用，请稍后重试")

        if not response.ok:
            raise HTTPException(status_code=502, detail="人机验证服务暂时不可用，请稍后重试")

        data = await response.json()
        try:
            success = data.success
            if success is None or str(success) in ("false", "False", "undefined", "null"):
                return False
            return True
        except Exception:
            return False

    async def send_verification_code(self, email: str, turnstile_token: str, remote_ip: str | None, db=None) -> None:
        try:
            # 1. Verify Turnstile
            valid = await self.verify_turnstile(turnstile_token, remote_ip)
            if not valid:
                raise HTTPException(status_code=400, detail="人机验证失败，请重试")

            # 2. Check if email is already registered
            if db is not None:
                from users.repository import UserRepository
                user_repo = UserRepository(db)
                existing_user = await user_repo.get_by_email(email)
                if existing_user:
                    raise HTTPException(status_code=409, detail="该邮箱已被注册")

            # 3. Check cooldown (separate key with shorter TTL)
            # KV.get() returns JS null (pyodide.ffi.jsnull) for missing keys,
            # which is falsy but is NOT Python None. Use truthiness check
            # instead of `is not None` to correctly handle jsnull.
            cooldown = await self.kv.get(f"email_cooldown:{email}")
            if cooldown is not None and cooldown:
                raise HTTPException(status_code=429, detail="验证码已发送，请稍后再试")

            # 4. Generate code
            code = self._generate_code()

            # 5. Store code in KV with full TTL
            await self.kv.put(f"email_code:{email}", code, expirationTtl=EMAIL_CODE_TTL)

            # 6. Send email — prefer Resend template when configured
            template_id = self._get_template_id()
            if template_id:
                await self._send_email_with_template(email, template_id, code)
            else:
                html = self._build_email_html(code)
                await self._send_email(email, "您的验证码", html)

            # 7. Set cooldown AFTER email is sent successfully
            #    This prevents 429 on retry if the email send failed
            await self.kv.put(f"email_cooldown:{email}", "1", expirationTtl=EMAIL_CODE_COOLDOWN)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=500, detail="服务器内部错误")

    async def verify_code(self, email: str, code: str) -> bool:
        stored = await self.kv.get(f"email_code:{email}")
        if stored is None or not stored:
            return False
        return str(stored) == code

    async def delete_code(self, email: str) -> None:
        await self.kv.delete(f"email_code:{email}")

    def _build_email_html(self, code: str) -> str:
        return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#fafafa;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="padding:40px 0;">
    <tr><td align="center">
      <table width="420" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:16px;padding:48px 40px;box-shadow:0 1px 3px rgba(0,0,0,0.06);">
        <tr><td style="text-align:center;padding-bottom:32px;">
          <div style="font-size:20px;font-weight:600;color:#0f172a;letter-spacing:-0.02em;">Cloudflare Auth</div>
        </td></tr>
        <tr><td style="text-align:center;padding-bottom:8px;">
          <div style="font-size:15px;color:#64748b;">您的邮箱验证码</div>
        </td></tr>
        <tr><td style="text-align:center;padding:24px 0 32px;">
          <div style="font-size:36px;font-weight:700;letter-spacing:8px;color:#0f172a;background:#f8fafc;border-radius:12px;padding:20px 0;border:1px solid #e2e8f0;">{code}</div>
        </td></tr>
        <tr><td style="text-align:center;padding-bottom:8px;">
          <div style="font-size:13px;color:#94a3b8;">验证码有效期为 5 分钟</div>
        </td></tr>
        <tr><td style="text-align:center;padding-top:24px;border-top:1px solid #f1f5f9;">
          <div style="font-size:12px;color:#cbd5e1;">如果您没有请求此验证码，请忽略此邮件。</div>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

    def _get_template_id(self) -> str | None:
        """Return the Resend template ID from env, or None if not configured."""
        try:
            tid = getattr(self.env, "RESEND_TEMPLATE_ID", None)
            if tid is None:
                return None
            s = str(tid)
            return None if s in ("", "undefined", "null") else s
        except Exception:
            return None

    async def _send_email_with_template(self, to_email: str, template_id: str, code: str) -> None:
        """Send verification code email via Resend template API."""
        from js import fetch, Headers

        headers = Headers.new()
        headers.set("Authorization", f"Bearer {self.env.RESEND_API_KEY}")
        headers.set("Content-Type", "application/json")

        body = json.dumps({
            "from": str(self.env.RESEND_FROM_EMAIL),
            "to": [to_email],
            "subject": "您的验证码",
            "template": {
                "id": template_id,
                "variables": {
                    RESEND_TEMPLATE_VARIABLE_NAME: code,
                },
            },
        })

        response = await fetch(
            RESEND_API_URL,
            method="POST",
            headers=headers,
            body=body,
        )

        if not response.ok:
            raise HTTPException(status_code=502, detail="邮件发送失败，请稍后重试")

    async def _send_email(self, to_email: str, subject: str, html: str) -> None:
        from js import fetch, Headers

        headers = Headers.new()
        headers.set("Authorization", f"Bearer {self.env.RESEND_API_KEY}")
        headers.set("Content-Type", "application/json")

        body = json.dumps({
            "from": str(self.env.RESEND_FROM_EMAIL),
            "to": [to_email],
            "subject": subject,
            "html": html,
        })

        response = await fetch(
            RESEND_API_URL,
            method="POST",
            headers=headers,
            body=body,
        )

        if not response.ok:
            raise HTTPException(status_code=502, detail="邮件发送失败，请稍后重试")
