#!/usr/bin/env python3
"""一键启动 Novel Agents 前后端服务。"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT / "frontend"
BACKEND_CLI = ROOT / ".venv" / "bin" / "novel"


def main() -> int:
    parser = argparse.ArgumentParser(description="同时启动后端 API 和前端仪表盘")
    parser.add_argument("--backend-port", type=int, default=8765, help="后端端口，默认 8765")
    parser.add_argument("--frontend-port", type=int, default=3000, help="前端端口，默认 3000")
    args = parser.parse_args()

    if not BACKEND_CLI.exists():
        print("未找到 .venv/bin/novel，请先在项目根目录执行：uv pip install -e \".[dev]\"")
        return 1

    if not (FRONTEND_DIR / "node_modules").exists():
        print("未找到 frontend/node_modules，请先执行：cd frontend && npm install")
        return 1

    warn_if_api_key_missing()

    frontend_env = os.environ.copy()
    frontend_env["NEXT_PUBLIC_API_BASE"] = f"http://127.0.0.1:{args.backend_port}"

    processes: list[subprocess.Popen[str]] = []
    try:
        processes.append(
            start_process(
                "后端",
                [str(BACKEND_CLI), "serve", "--port", str(args.backend_port)],
                ROOT,
                child_env(os.environ.copy()),
            )
        )
        processes.append(
            start_process(
                "前端",
                ["npm", "run", "dev", "--", "-p", str(args.frontend_port)],
                FRONTEND_DIR,
                child_env(frontend_env),
            )
        )

        print()
        print(f"前端页面: http://127.0.0.1:{args.frontend_port}")
        print(f"后端 API: http://127.0.0.1:{args.backend_port}")
        print("按 Ctrl+C 可同时停止前后端。")
        print(flush=True)

        while True:
            for proc in processes:
                code = proc.poll()
                if code is not None:
                    print(f"进程已退出，退出码：{code}，正在停止其它服务...", flush=True)
                    return code
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n收到 Ctrl+C，正在停止前后端...", flush=True)
        return 0
    finally:
        stop_processes(processes)


def child_env(base: dict[str, str]) -> dict[str, str]:
    """子进程使用无缓冲输出，便于实时查看日志。"""
    env = dict(base)
    env["PYTHONUNBUFFERED"] = "1"
    env.setdefault("FORCE_COLOR", "1")
    return env


def start_process(
    name: str,
    command: list[str],
    cwd: Path,
    env: dict[str, str],
) -> subprocess.Popen[str]:
    proc = subprocess.Popen(
        command,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,
    )
    thread = threading.Thread(target=stream_output, args=(name, proc), daemon=True)
    thread.start()
    return proc


def stream_output(name: str, proc: subprocess.Popen[str]) -> None:
    assert proc.stdout is not None
    while True:
        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                break
            time.sleep(0.05)
            continue
        sys.stdout.write(f"[{name}] {line}")
        sys.stdout.flush()


def stop_processes(processes: list[subprocess.Popen[str]]) -> None:
    for proc in processes:
        if proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass

    deadline = time.time() + 5
    for proc in processes:
        while proc.poll() is None and time.time() < deadline:
            time.sleep(0.1)
        if proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass


def warn_if_api_key_missing() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        print(
            "提示：未找到 .env。请复制 .env.example 并配置 APIMART_API_KEY，"
            "否则仪表盘无法启动章节流水线。",
            flush=True,
        )
        return

    api_key = ""
    for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip().startswith("APIMART_API_KEY="):
            api_key = line.split("=", 1)[1].strip()
            break

    if not api_key or api_key == "your-apimart-api-key-here":
        print(
            "提示：.env 中还没有有效的 APIMART_API_KEY，"
            "仪表盘创作流水线将无法调用 LLM。",
            flush=True,
        )


if __name__ == "__main__":
    sys.exit(main())
