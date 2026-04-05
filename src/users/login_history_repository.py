import uuid


def _d1_val(v):
    """Convert None to empty string for D1 binding in Pyodide.
    In the Pyodide environment, Python None becomes JS undefined which D1 rejects.
    Use empty string as a safe fallback for nullable text columns."""
    return "" if v is None else v


class LoginHistoryRepository:
    def __init__(self, db):
        self.db = db  # D1 binding

    async def create_record(self, user_id: str, action: str, method: str | None,
                            ip: str | None, country: str | None, city: str | None,
                            region: str | None, user_agent: str | None) -> None:
        """Insert a login/logout history record."""
        record_id = str(uuid.uuid4())
        await self.db.prepare(
            "INSERT INTO login_history (id, user_id, action, method, ip, country, city, region, user_agent) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        ).bind(record_id, user_id, action,
               _d1_val(method), _d1_val(ip), _d1_val(country),
               _d1_val(city), _d1_val(region), _d1_val(user_agent)).run()

    async def get_by_user(self, user_id: str, page: int = 1, page_size: int = 20) -> list[dict]:
        """Paginated query of user login history, ordered by created_at descending."""
        offset = (page - 1) * page_size
        result = await self.db.prepare(
            "SELECT id, user_id, action, method, ip, country, city, region, user_agent, created_at "
            "FROM login_history WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?"
        ).bind(user_id, page_size, offset).run()
        return [row.to_py() for row in (result.results or [])]

    async def count_by_user(self, user_id: str) -> int:
        """Count total login history records for a user."""
        result = await self.db.prepare(
            "SELECT COUNT(*) as total FROM login_history WHERE user_id = ?"
        ).bind(user_id).first()
        if result:
            data = result.to_py()
            return data.get("total", 0)
        return 0
