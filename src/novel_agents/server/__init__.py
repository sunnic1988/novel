"""FastAPI 服务端 — 为前端仪表盘提供 REST + WebSocket 接口"""

from novel_agents.server.app import create_app

__all__ = ["create_app"]
