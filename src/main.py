from workers import WorkerEntrypoint
from fastapi import FastAPI
from pydantic import BaseModel
import asgi
from auth.router import auth_router
from auth.oauth_router import oauth_router
from users.router import users_router


_schema_initialized = False


async def _init_schema(env):
    """应用启动时执行 D1 建表 SQL"""
    global _schema_initialized
    if _schema_initialized:
        return
    try:
        with open("schema.sql", "r") as f:
            sql = f.read()
        # D1 不支持一次执行多条语句，需要逐条执行
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        for stmt in statements:
            await env.DB.prepare(stmt).run()
        _schema_initialized = True
    except Exception:
        # 表可能已存在，忽略错误继续运行
        _schema_initialized = True


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        await _init_schema(self.env)
        # 将 Cloudflare cf 对象挂载到 env 上，以便路由处理器获取地理位置信息
        # asgi.request_to_scope 不会将 cf 传入 ASGI scope，因此通过 env 传递
        try:
            self.env._cf = request.js_object.cf
        except Exception:
            self.env._cf = None
        return await asgi.fetch(app, request, self.env)


app = FastAPI()
app.include_router(auth_router)
app.include_router(oauth_router)
app.include_router(users_router)


# 定义请求数据模型
class UserQuery(BaseModel):
    name: str


@app.post("/greet")
async def greet(query: UserQuery):
    # 模拟简单的逻辑处理
    greeting = f"Hi {query.name}, this response was generated at the edge."
    return {
        "success": True,
        "payload": greeting
    }
