import uuid


def _d1_val(v):
    """Convert None to empty string for D1 binding in Pyodide.
    In the Pyodide environment, Python None becomes JS undefined which D1 rejects.
    Use empty string as a safe fallback for nullable text columns."""
    return "" if v is None else v


class UserRepository:
    def __init__(self, db):
        self.db = db  # D1 binding

    async def create_user(self, username: str, email: str, password_hash: str, role: str = "user") -> dict:
        """Create a new user with password."""
        user_id = str(uuid.uuid4())
        await self.db.prepare(
            "INSERT INTO users (id, username, email, password_hash, role) VALUES (?, ?, ?, ?, ?)"
        ).bind(user_id, username, email, password_hash, role).run()
        return {
            "id": user_id,
            "username": username,
            "email": email,
            "role": role,
        }

    async def create_user_without_password(self, username: str, email: str, role: str = "user") -> dict:
        """Create a new user without password (for OAuth registration)."""
        user_id = str(uuid.uuid4())
        await self.db.prepare(
            "INSERT INTO users (id, username, email, role) VALUES (?, ?, ?, ?)"
        ).bind(user_id, username, email, role).run()
        return {
            "id": user_id,
            "username": username,
            "email": email,
            "role": role,
        }

    async def get_by_email(self, email: str) -> dict | None:
        """Find user by email."""
        result = await self.db.prepare(
            "SELECT id, username, email, password_hash, role, created_at FROM users WHERE email = ? LIMIT 1"
        ).bind(email).first()
        return result.to_py() if result else None

    async def get_by_username(self, username: str) -> dict | None:
        """Find user by username."""
        result = await self.db.prepare(
            "SELECT id, username, email, password_hash, role, created_at FROM users WHERE username = ? LIMIT 1"
        ).bind(username).first()
        return result.to_py() if result else None

    async def get_by_id(self, user_id: str) -> dict | None:
        """Find user by ID."""
        result = await self.db.prepare(
            "SELECT id, username, email, password_hash, role, created_at FROM users WHERE id = ? LIMIT 1"
        ).bind(user_id).first()
        return result.to_py() if result else None

    async def get_oauth_account(self, provider: str, provider_user_id: str) -> dict | None:
        """Find OAuth account by provider and provider user ID, joined with user data."""
        result = await self.db.prepare(
            "SELECT oa.id as oauth_id, oa.user_id, oa.provider, oa.provider_user_id, "
            "u.id, u.username, u.email, u.role, u.created_at "
            "FROM oauth_accounts oa JOIN users u ON oa.user_id = u.id "
            "WHERE oa.provider = ? AND oa.provider_user_id = ? LIMIT 1"
        ).bind(provider, provider_user_id).first()
        return result.to_py() if result else None

    async def create_oauth_account(self, user_id: str, provider: str, provider_user_id: str,
                                   provider_email: str = None, provider_name: str = None,
                                   provider_avatar_url: str = None, access_token_expires_at: str = None) -> None:
        """Create an OAuth account link with detailed provider info."""
        oauth_id = str(uuid.uuid4())
        await self.db.prepare(
            "INSERT INTO oauth_accounts (id, user_id, provider, provider_user_id, provider_email, provider_name, provider_avatar_url, access_token_expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        ).bind(oauth_id, user_id, provider, provider_user_id,
               _d1_val(provider_email), _d1_val(provider_name),
               _d1_val(provider_avatar_url), _d1_val(access_token_expires_at)).run()

    async def update_oauth_account(self, provider: str, provider_user_id: str,
                                    provider_email: str = None, provider_name: str = None,
                                    provider_avatar_url: str = None, access_token_expires_at: str = None) -> None:
        """Update OAuth account info on each login."""
        await self.db.prepare(
            "UPDATE oauth_accounts SET provider_email = ?, provider_name = ?, provider_avatar_url = ?, "
            "access_token_expires_at = ?, updated_at = datetime('now') "
            "WHERE provider = ? AND provider_user_id = ?"
        ).bind(_d1_val(provider_email), _d1_val(provider_name),
               _d1_val(provider_avatar_url), _d1_val(access_token_expires_at),
               provider, provider_user_id).run()

    async def update_password(self, user_id: str, password_hash: str) -> None:
        """Set password for an OAuth user."""
        await self.db.prepare(
            "UPDATE users SET password_hash = ? WHERE id = ?"
        ).bind(password_hash, user_id).run()

    async def get_oauth_accounts_by_user(self, user_id: str) -> list[dict]:
        """Get all OAuth accounts linked to a user with detailed info."""
        result = await self.db.prepare(
            "SELECT id, user_id, provider, provider_user_id, provider_email, provider_name, "
            "provider_avatar_url, access_token_expires_at, created_at, updated_at "
            "FROM oauth_accounts WHERE user_id = ?"
        ).bind(user_id).run()
        return [row.to_py() for row in (result.results or [])]
