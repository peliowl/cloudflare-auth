# Token expiration
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7
REFRESH_TOKEN_EXPIRE_MINUTES = REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60

# OAuth state TTL (seconds)
OAUTH_STATE_TTL = 300

# Email verification code
EMAIL_CODE_TTL = 300  # seconds
EMAIL_CODE_COOLDOWN = 60  # seconds (frontend countdown)
RESEND_API_URL = "https://api.resend.com/emails"
TURNSTILE_SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

# OAuth Provider endpoints
OAUTH_PROVIDERS = {
    "google": {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v2/userinfo",
        "scope": "openid email profile",
    },
}
