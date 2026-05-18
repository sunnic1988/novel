"""FastAPI 服务端 — 为前端仪表盘提供 REST + WebSocket 接口"""

def create_app():
    from novel_agents.server.app import create_app as _create_app

    return _create_app()


__all__ = ["create_app"]
