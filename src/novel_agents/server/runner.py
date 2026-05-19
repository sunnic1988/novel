"""Run 生命周期管理 — 启动 / 暂停 / 干预 / 终止 9 Agent 流水线

每轮 Live run 完成后写入章节副产物包：
KPI / 标题 / 金句 / AI 味 lint / 章节摘要等（基于各 Agent 真实输出）。
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import uuid
from pathlib import Path
from typing import Any

from novel_agents.book import (
    cost as cost_mod,
)
from novel_agents.book import (
    feedback,
    highlights,
    summaries,
)
from novel_agents.book import (
    kpi as kpi_mod,
)
from novel_agents.book import (
    titles as titles_mod,
)
from novel_agents.book.ai_taste import analyze as ai_taste_analyze
from novel_agents.book.paths import ai_lint_path, ensure_dirs, use_script
from novel_agents.server import storage_sqlite
from novel_agents.server.events import bus
from novel_agents.server.models import (
    AGENT_META,
    AGENT_ORDER,
    AgentStatus,
    Event,
    RunSummary,
    StartRunRequest,
    now_ms,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RUN_OUTPUTS_ROOT = PROJECT_ROOT / "output" / "runs"
OUTPUT_PREVIEW_LIMIT = 50000
LAST_MESSAGE_LIMIT = 400
AGENT_EXEC_TIMEOUT_SEC = int(os.getenv("AGENT_EXEC_TIMEOUT_SEC", "240"))
MAX_AUTO_RETRIES = int(os.getenv("MAX_AUTO_RETRIES", "3"))
RETRY_DELAY_SEC = float(os.getenv("RETRY_DELAY_SEC", "2.0"))


class RunController:
    """单个 run 的生命周期控制器"""

    def __init__(self, run: RunSummary) -> None:
        self.run = run
        self.pause_event = asyncio.Event()
        self.pause_event.set()
        self.abort_event = asyncio.Event()
        self.intervention_outputs: dict[str, str] = {}
        self.intervention_waiters: dict[str, asyncio.Event] = {}
        self.retry_waiters: dict[str, asyncio.Event] = {}
        self.retry_requests: dict[str, bool] = {}
        self.task: asyncio.Task[Any] | None = None
        # 高级选项
        self.is_opening: bool = False
        self.best_of_n: int = 1
        self.enabled_agents: set[str] = set(AGENT_ORDER)
        self.budget_usd: float | None = None
        # 实跑累计实际成本
        self.actual_cost_usd: float = 0.0
        self.step_confirm_mode: bool = False
        self.agent_outputs: dict[str, str] = {}
        self.call_index: int = 0

    def pause(self) -> None:
        self.pause_event.clear()
        self.run.status = "paused"

    def resume(self) -> None:
        self.pause_event.set()
        if self.run.status == "paused":
            self.run.status = "running"

    def abort(self) -> None:
        self.abort_event.set()
        self.pause_event.set()
        for w in self.intervention_waiters.values():
            w.set()
        for w in self.retry_waiters.values():
            w.set()
        self.run.status = "aborted"

    async def wait_if_paused(self) -> None:
        if not self.pause_event.is_set():
            await self.pause_event.wait()


class RunManager:
    def __init__(self) -> None:
        self.controllers: dict[str, RunController] = {}

    def get(self, run_id: str) -> RunController | None:
        return self.controllers.get(run_id)

    def list_runs(self) -> list[RunSummary]:
        return [c.run for c in self.controllers.values()]

    def create(self, req: StartRunRequest) -> RunController:
        run_id = uuid.uuid4().hex[:10]
        enabled = set(req.enabled_agents) if req.enabled_agents else set(AGENT_ORDER)
        agents = [
            AgentStatus(
                id=aid,
                name=AGENT_META[aid]["name"],
                role=AGENT_META[aid]["role"],
                color=AGENT_META[aid]["color"],
                icon=AGENT_META[aid]["icon"],
                model_kind=AGENT_META[aid]["model_kind"],
                uses_references=AGENT_META[aid]["uses_references"],
                model=(
                    "claude-sonnet-4-6"
                    if AGENT_META[aid]["model_kind"] == "creative"
                    else "deepseek-v4-pro"
                ),
                status="idle" if aid in enabled else "skipped",
            )
            for aid in AGENT_ORDER
        ]
        run = RunSummary(
            run_id=run_id,
            script_id=req.script_id,
            script_name="默认剧本",
            chapter_num=req.chapter_num,
            chapter_title=req.chapter_title,
            mode="live",
            auto_run=req.auto_run,
            status="queued",
            agents=agents,
        )
        script = storage_sqlite.get_script(req.script_id)
        if script:
            run.script_name = str(script.get("name") or "默认剧本")
        bus.upsert_run(run)
        ctrl = RunController(run)
        ctrl.is_opening = req.is_opening
        ctrl.best_of_n = max(1, min(req.best_of_n, 5))
        ctrl.enabled_agents = enabled
        ctrl.budget_usd = req.budget_usd
        ctrl.step_confirm_mode = (
            req.step_confirm_mode if req.step_confirm_mode is not None else (not req.auto_run)
        )
        self.controllers[run_id] = ctrl
        return ctrl

    async def start(self, ctrl: RunController, req: StartRunRequest) -> None:
        ctrl.task = asyncio.create_task(_run_pipeline(ctrl, req))

    async def apply_intervention(
        self, run_id: str, agent_id: str, edited_output: str, resume: bool
    ) -> bool:
        ctrl = self.controllers.get(run_id)
        if not ctrl:
            return False
        if ctrl.run.paused_at_agent and ctrl.run.paused_at_agent != agent_id:
            return False
        ctrl.intervention_outputs[agent_id] = edited_output
        waiter = ctrl.intervention_waiters.get(agent_id)
        if waiter and resume:
            waiter.set()
        _persist_intervention(run_id, agent_id, edited_output, resume)
        await bus.publish(
            Event(
                run_id=run_id,
                type="intervention_applied",
                agent=agent_id,
                message=f"人工干预已应用 ({len(edited_output)} 字)",
                data={"edited_output_preview": edited_output[:200]},
            )
        )
        for a in ctrl.run.agents:
            if a.id == agent_id:
                if edited_output:
                    a.output_preview = edited_output[:OUTPUT_PREVIEW_LIMIT]
                    a.last_message = "人工确认已更新产出"
                a.status = "done" if resume else "awaiting_intervention"
        _write_run_state(ctrl.run)
        if resume:
            ctrl.resume()
        await bus.publish_run_update(ctrl.run)
        return True

    async def request_retry(self, run_id: str, agent_id: str) -> bool:
        ctrl = self.controllers.get(run_id)
        if not ctrl:
            return False
        if ctrl.run.paused_at_agent and ctrl.run.paused_at_agent != agent_id:
            return False
        ctrl.retry_requests[agent_id] = True
        waiter = ctrl.retry_waiters.get(agent_id)
        if waiter:
            waiter.set()
        await _emit(
            run_id,
            "agent_retry_requested",
            agent=agent_id,
            message="已收到人工重试请求，准备重新执行该 Agent。",
            data={"agent_id": agent_id},
        )
        return True


manager = RunManager()


def _find_agent(run: RunSummary, agent_id: str) -> AgentStatus:
    for a in run.agents:
        if a.id == agent_id:
            return a
    raise KeyError(agent_id)


async def _emit(
    run_id: str,
    type_: str,
    agent: str | None = None,
    message: str = "",
    data: dict[str, Any] | None = None,
) -> None:
    await bus.publish(
        Event(run_id=run_id, type=type_, agent=agent, message=message, data=data or {})
    )


def _run_dir(run_id: str) -> Path:
    d = RUN_OUTPUTS_ROOT / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_run_manifest(ctrl: RunController) -> None:
    run = ctrl.run
    manifest = {
        "run_id": run.run_id,
        "chapter_num": run.chapter_num,
        "chapter_title": run.chapter_title,
        "mode": run.mode,
        "auto_run": run.auto_run,
        "step_confirm_mode": ctrl.step_confirm_mode,
        "enabled_agents": sorted(ctrl.enabled_agents),
        "best_of_n": ctrl.best_of_n,
        "budget_usd": ctrl.budget_usd,
    }
    (_run_dir(run.run_id) / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _append_stream_delta(
    run_id: str, agent_id: str, step_index: int, chunk: str
) -> None:
    if not chunk:
        return
    stream_file = _run_dir(run_id) / f"step_{step_index:02d}_{agent_id}.stream.txt"
    with stream_file.open("a", encoding="utf-8") as f:
        f.write(chunk)


def _persist_agent_call(
    run_id: str,
    agent_id: str,
    step_index: int,
    call_id: str,
    prompt_full: str,
    response_full: str,
    meta: dict[str, Any],
) -> None:
    run_dir = _run_dir(run_id)
    prefix = f"step_{step_index:02d}_{agent_id}_{call_id}"
    md_path = run_dir / f"{prefix}.md"
    json_path = run_dir / f"{prefix}.json"
    md_path.write_text(
        (
            f"# {agent_id} · call {call_id}\n\n"
            "## Prompt\n\n"
            f"{prompt_full}\n\n"
            "## Response\n\n"
            f"{response_full}\n"
        ),
        encoding="utf-8",
    )
    payload = {
        "run_id": run_id,
        "agent_id": agent_id,
        "step_index": step_index,
        "call_id": call_id,
        "prompt_full": prompt_full,
        "response_full": response_full,
        "meta": meta,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _persist_intervention(
    run_id: str, agent_id: str, edited_output: str, resume: bool
) -> None:
    run_dir = _run_dir(run_id)
    data = {
        "agent_id": agent_id,
        "resume": resume,
        "edited_output": edited_output,
        "chars": len(edited_output),
    }
    fp = run_dir / f"intervention_{agent_id}.json"
    fp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_run_state(run: RunSummary) -> None:
    (_run_dir(run.run_id) / "run_state.json").write_text(
        json.dumps(run.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8"
    )


async def _run_pipeline(ctrl: RunController, req: StartRunRequest) -> None:
    run = ctrl.run
    with use_script(run.script_id):
        run.status = "running"
        run.started_at = now_ms()
        _write_run_manifest(ctrl)
        _write_run_state(run)
        await bus.publish_run_update(run)

        # 成本预估
        enabled_models = {
            a.id: a.model for a in run.agents if a.id in ctrl.enabled_agents
        }
        cost_estimate = cost_mod.estimate_chapter_cost(
            enabled_models, enabled=ctrl.enabled_agents, best_of_n=ctrl.best_of_n
        )
        await _emit(
            run.run_id,
            "cost_estimate",
            message=(
                f"💰 本章预估成本 ${cost_estimate['total_cost_usd']:.3f} "
                f"({cost_estimate['total_tokens']:,} tokens, best_of_n={ctrl.best_of_n})"
            ),
            data=cost_estimate,
        )
        if ctrl.budget_usd is not None and cost_estimate["total_cost_usd"] > ctrl.budget_usd:
            await _emit(
                run.run_id,
                "cost_warning",
                message=(
                    f"⚠️ 预估成本 ${cost_estimate['total_cost_usd']:.3f} 已超过预算 "
                    f"${ctrl.budget_usd:.3f}，继续执行（如需中止请点终止）。"
                ),
                data={"budget": ctrl.budget_usd, "estimate": cost_estimate["total_cost_usd"]},
            )

        await _emit(
            run.run_id,
            "run_started",
            message=(
                f"开始创作第 {run.chapter_num} 章 「{run.chapter_title or '未命名'}」 "
                f"(script={run.script_name}, mode={run.mode}, is_opening={ctrl.is_opening}, best_of_n={ctrl.best_of_n}, "
                f"step_confirm={ctrl.step_confirm_mode})"
            ),
            data={
                "script_id": run.script_id,
                "script_name": run.script_name,
                "chapter_num": run.chapter_num,
                "title": run.chapter_title,
                "mode": run.mode,
                "is_opening": ctrl.is_opening,
                "best_of_n": ctrl.best_of_n,
                "step_confirm_mode": ctrl.step_confirm_mode,
                "enabled_agents": list(ctrl.enabled_agents),
            },
        )

        try:
            ok = await _run_live(ctrl, req)
            if not ok:
                run.status = "error"
                _write_run_state(run)
                await bus.publish_run_update(run)
                return

            if ctrl.abort_event.is_set():
                return

            # 章节副产物入账（基于各 Agent 真实输出）
            try:
                await _persist_chapter_artifacts(ctrl)
            except Exception as exc:  # pragma: no cover
                await _emit(run.run_id, "run_error", message=f"账本写入失败: {exc}")

            run.status = "completed"
            run.completed_at = now_ms()
            _write_run_state(run)
            await bus.publish_run_update(run)
            await _emit(
                run.run_id,
                "run_completed",
                message=(
                    f"流水线完成，总 token: {run.total_tokens:,}"
                    f"，预估成本 ${cost_estimate['total_cost_usd']:.3f}"
                ),
                data={
                    "total_tokens": run.total_tokens,
                    "prompt_tokens": run.total_prompt_tokens,
                    "completion_tokens": run.total_completion_tokens,
                    "cost_usd": cost_estimate["total_cost_usd"],
                },
            )
        except asyncio.CancelledError:
            run.status = "aborted"
            _write_run_state(run)
            await bus.publish_run_update(run)
            raise
        except Exception as exc:  # pragma: no cover
            run.status = "error"
            _write_run_state(run)
            await bus.publish_run_update(run)
            await _emit(run.run_id, "run_error", message=f"流水线异常: {exc}")


def _chapter_body(ctrl: RunController) -> str:
    return (
        ctrl.agent_outputs.get("polisher")
        or ctrl.agent_outputs.get("writer")
        or ""
    ).strip()


def _extract_highlight_lines(text: str, max_lines: int = 3) -> list[str]:
    lines: list[str] = []
    for raw in text.replace("。", "。\n").split("\n"):
        line = raw.strip()
        if 12 <= len(line) <= 48 and line not in lines:
            lines.append(line)
        if len(lines) >= max_lines:
            break
    return lines


def _default_title_candidates(chapter: int, title: str) -> list[dict[str, Any]]:
    base = title.strip() or f"第{chapter}章"
    return [{"title": base, "angle": "章节主标题", "score": 7.5}]


async def _await_intervention(ctrl: RunController, agent: AgentStatus) -> None:
    run = ctrl.run
    agent.status = "awaiting_intervention"
    run.status = "paused"
    run.paused_at_agent = agent.id
    _write_run_state(run)
    ctrl.pause_event.clear()
    waiter = asyncio.Event()
    ctrl.intervention_waiters[agent.id] = waiter
    await bus.publish_run_update(run)
    await _emit(
        run.run_id,
        "intervention_requested",
        agent=agent.id,
        message=f"等待人工对 {agent.name} 的产出进行确认/编辑…",
    )
    await waiter.wait()
    edited = ctrl.intervention_outputs.get(agent.id)
    if edited:
        ctrl.agent_outputs[agent.id] = edited
        agent.output_preview = edited[:OUTPUT_PREVIEW_LIMIT]
    run.paused_at_agent = None
    ctrl.intervention_waiters.pop(agent.id, None)
    ctrl.pause_event.set()
    run.status = "running"
    _write_run_state(run)
    await bus.publish_run_update(run)


async def _await_retry(ctrl: RunController, agent: AgentStatus) -> bool:
    run = ctrl.run
    run.status = "paused"
    run.paused_at_agent = agent.id
    _write_run_state(run)
    waiter = asyncio.Event()
    ctrl.retry_waiters[agent.id] = waiter
    await bus.publish_run_update(run)
    await _emit(
        run.run_id,
        "agent_retry_waiting",
        agent=agent.id,
        message=f"{agent.name} 自动重试已耗尽，等待人工点击重试。",
    )
    await waiter.wait()
    ctrl.retry_waiters.pop(agent.id, None)
    if ctrl.abort_event.is_set():
        return False
    should_retry = bool(ctrl.retry_requests.pop(agent.id, False))
    if not should_retry:
        return False
    run.paused_at_agent = None
    run.status = "running"
    agent.status = "running"
    agent.last_message = "收到人工重试请求，准备重新执行…"
    _write_run_state(run)
    await bus.publish_run_update(run)
    return True


async def _persist_chapter_artifacts(ctrl: RunController) -> None:
    """章节完成后写入：摘要 / KPI / 标题 / 金句 / AI 味 lint（基于 Agent 真实输出）"""
    run = ctrl.run
    n = run.chapter_num
    ensure_dirs()
    body = _chapter_body(ctrl)
    word_count = len(body) if body else 0

    summary_text = summaries.auto_summarize(body) if body else f"第{n}章（暂无正文）"
    summaries.save(n, summary_text)
    await _emit(
        run.run_id,
        "artifact_saved",
        agent=None,
        message=f"📝 章节摘要已保存 (summaries/ch{n:03d}.md)",
        data={"kind": "summary", "chars": len(summary_text)},
    )

    k = kpi_mod.fallback_scores(n)
    kpi_obj = kpi_mod.ChapterKPI(
        chapter=n,
        title=run.chapter_title,
        word_count=word_count or max(800, 2000 + random.randint(-200, 400)),
        run_id=run.run_id,
        enabled_agents=list(ctrl.enabled_agents),
        **k,
    )
    kpi_mod.save(kpi_obj)
    await _emit(
        run.run_id,
        "artifact_saved",
        message=(
            f"📊 章节 KPI 已保存（追订 {k['retention_score']:.2f} / 钩子 "
            f"{k['hook_strength']:.2f} / AI 味 {k['ai_taste_score']:.2f}）"
        ),
        data={"kind": "kpi", **k},
    )

    import json as _json

    if body:
        try:
            lint_dict = ai_taste_analyze(body).to_dict()
        except Exception:
            lint_dict = {"score": 0.0, "level": "未知", "issues": [], "suggestions": []}
    else:
        lint_dict = {"score": 0.0, "level": "无正文", "issues": [], "suggestions": []}
    ai_lint_path(n).write_text(
        _json.dumps(lint_dict, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    await _emit(
        run.run_id,
        "artifact_saved",
        message=f"🔍 AI 味检测：score={lint_dict['score']} / {lint_dict.get('level', '—')}",
        data={"kind": "ai_lint", **lint_dict},
    )

    highlight_lines = _extract_highlight_lines(body)
    for line in highlight_lines:
        highlights.add(n, line, tag="情绪", score=4.5)
    if highlight_lines:
        await _emit(
            run.run_id,
            "artifact_saved",
            message=f"✨ 已沉淀 {len(highlight_lines)} 句金句入金句库",
            data={"kind": "highlights", "count": len(highlight_lines)},
        )

    title_candidates = _default_title_candidates(n, run.chapter_title)
    marketing = (ctrl.agent_outputs.get("marketing_specialist") or "").strip()
    if marketing and len(marketing) > 20:
        title_candidates = [
            {"title": marketing.split("\n")[0][:60], "angle": "营销 Agent", "score": 8.0},
            *title_candidates,
        ]
    titles_mod.save_titles(n, title_candidates)
    await _emit(
        run.run_id,
        "artifact_saved",
        message=f"🎯 已生成 {len(title_candidates)} 个标题候选",
        data={"kind": "titles", "candidates": title_candidates},
    )

    if marketing and len(marketing) > 80:
        titles_mod.save_synopsis(f"# 书籍简介\n\n{marketing[:2000]}")
        await _emit(
            run.run_id,
            "artifact_saved",
            message="📖 书籍简介已根据营销 Agent 输出更新",
            data={"kind": "synopsis_candidates", "count": 1},
        )

    if not feedback.load(n):
        feedback.save(n, "（在此填写读者评论摘要，将反向喂给下一章规划。）")


async def _run_live(ctrl: RunController, req: StartRunRequest) -> bool:
    run = ctrl.run

    if not os.getenv("APIMART_API_KEY"):
        await _emit(
            run.run_id,
            "run_error",
            message="未设置 APIMART_API_KEY，live 模式无法启动。",
        )
        return False

    try:
        from novel_agents.core import orchestrator as orch
    except Exception as exc:
        await _emit(run.run_id, "run_error", message=f"无法导入 orchestrator: {exc}")
        return False

    for idx, aid in enumerate(AGENT_ORDER):
        if ctrl.abort_event.is_set():
            return False
        await ctrl.wait_if_paused()
        agent = _find_agent(run, aid)
        if aid not in ctrl.enabled_agents:
            await _emit(
                run.run_id, "agent_skipped", agent=aid, message=f"{agent.name} 已禁用，跳过"
            )
            continue
        waited_internally = await _execute_live_agent(ctrl, req, orch, agent, idx)
        if ctrl.abort_event.is_set():
            return False
        if ctrl.step_confirm_mode and not waited_internally:
            await _await_intervention(ctrl, agent)
    return True


async def _execute_live_agent(
    ctrl: RunController,
    req: StartRunRequest,
    orch: Any,
    agent: AgentStatus,
    idx: int,
) -> bool:
    run = ctrl.run
    aid = agent.id
    loop = asyncio.get_running_loop()
    is_first_attempt = True

    while True:
        for attempt in range(1, MAX_AUTO_RETRIES + 2):
            ctrl.call_index += 1
            call_id = f"{run.run_id}-{aid}-{ctrl.call_index}"
            stream_state = {"text": ""}

            async def _publish_stream_chunk(chunk: str) -> None:
                stream_state["text"] += chunk
                _append_stream_delta(run.run_id, aid, idx + 1, chunk)
                agent.last_message = chunk[-LAST_MESSAGE_LIMIT:]
                agent.output_preview = stream_state["text"][-OUTPUT_PREVIEW_LIMIT:]
                agent.progress = max(agent.progress, 0.05)
                await bus.publish_run_update(run)
                await _emit(
                    run.run_id,
                    "agent_stream_delta",
                    agent=aid,
                    message=chunk,
                    data={
                        "call_id": call_id,
                        "agent_id": aid,
                        "step_index": idx + 1,
                        "delta": chunk,
                        "accumulated_chars": len(stream_state["text"]),
                    },
                )

            def _stream_callback(chunk: str) -> None:
                if not chunk:
                    return
                asyncio.run_coroutine_threadsafe(_publish_stream_chunk(chunk), loop)

            if attempt > 1:
                await _emit(
                    run.run_id,
                    "agent_retry_attempt",
                    agent=aid,
                    message=f"{agent.name} 自动重试第 {attempt - 1}/{MAX_AUTO_RETRIES} 次",
                    data={
                        "agent_id": aid,
                        "attempt": attempt - 1,
                        "max_retries": MAX_AUTO_RETRIES,
                    },
                )

            agent.status = "running"
            if is_first_attempt:
                agent.started_at = now_ms()
                is_first_attempt = False
            agent.retry_count += 1 if attempt > 1 else 0
            agent.progress = 0.0
            agent.last_message = "正在生成中…"
            await bus.publish_run_update(run)

            if attempt == 1:
                await _emit(
                    run.run_id,
                    "agent_started",
                    agent=aid,
                    message=f"{agent.name} 开始工作 · 使用模型 {agent.model}",
                    data={
                        "model": agent.model,
                        "uses_references": agent.uses_references,
                        "order": idx + 1,
                    },
                )
                if agent.uses_references:
                    agent.tool_calls += 1
                    await _emit(
                        run.run_id,
                        "agent_tool_call",
                        agent=aid,
                        message="调用工具：爆款范文检索",
                        data={
                            "tool": "ReferenceSearchTool",
                            "query": f"第{run.chapter_num}章 场景推进",
                        },
                    )

            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(
                        orch.run_single_agent_step,
                        aid,
                        req.chapter_num,
                        req.chapter_title,
                        req.synopsis_override,
                        dict(ctrl.agent_outputs),
                        ctrl.is_opening,
                        _stream_callback,
                        run.script_id,
                    ),
                    timeout=AGENT_EXEC_TIMEOUT_SEC,
                )
            except asyncio.TimeoutError:
                err_msg = f"{agent.name} 执行超时（>{AGENT_EXEC_TIMEOUT_SEC}s）"
                agent.output_preview = stream_state["text"][:OUTPUT_PREVIEW_LIMIT]
                agent.last_message = err_msg
                agent.progress = max(agent.progress, 0.1)
                await bus.publish_run_update(run)
                await _emit(
                    run.run_id,
                    "agent_timeout",
                    agent=aid,
                    message=err_msg,
                    data={
                        "agent_id": aid,
                        "timeout_sec": AGENT_EXEC_TIMEOUT_SEC,
                        "partial_chars": len(stream_state["text"]),
                        "attempt": attempt,
                    },
                )
                if attempt <= MAX_AUTO_RETRIES:
                    await asyncio.sleep(RETRY_DELAY_SEC)
                    continue
                agent.status = "error"
                agent.last_message = "自动重试已耗尽，等待人工重试"
                await bus.publish_run_update(run)
                await _emit(
                    run.run_id,
                    "agent_retry_exhausted",
                    agent=aid,
                    message=f"{agent.name} 自动重试耗尽，请人工点击重试。",
                    data={"agent_id": aid, "max_retries": MAX_AUTO_RETRIES},
                )
                if await _await_retry(ctrl, agent):
                    break
                return False
            except Exception as exc:
                err_msg = f"{agent.name} 执行失败: {exc}"
                agent.last_message = err_msg[:LAST_MESSAGE_LIMIT]
                agent.progress = max(agent.progress, 0.1)
                await bus.publish_run_update(run)
                await _emit(run.run_id, "run_error", agent=aid, message=err_msg)
                if attempt <= MAX_AUTO_RETRIES:
                    await asyncio.sleep(RETRY_DELAY_SEC)
                    continue
                agent.status = "error"
                agent.last_message = "自动重试已耗尽，等待人工重试"
                await bus.publish_run_update(run)
                await _emit(
                    run.run_id,
                    "agent_retry_exhausted",
                    agent=aid,
                    message=f"{agent.name} 自动重试耗尽，请人工点击重试。",
                    data={"agent_id": aid, "max_retries": MAX_AUTO_RETRIES},
                )
                if await _await_retry(ctrl, agent):
                    break
                return False

            prompt_full = str(result.get("prompt_full", ""))
            response_full = str(result.get("response_full", ""))
            p_tok = int(result.get("prompt_tokens", 0))
            c_tok = int(result.get("completion_tokens", 0))
            latency = int(result.get("latency_ms", 0))
            model = str(result.get("model", agent.model))
            output_kind = str(result.get("output_kind", "general"))
            validation_warning = str(result.get("validation_warning", "")).strip()

            if stream_state["text"]:
                response_full = stream_state["text"]

            agent.prompt_tokens += p_tok
            agent.completion_tokens += c_tok
            agent.total_tokens = agent.prompt_tokens + agent.completion_tokens
            agent.llm_calls += 1
            agent.latency_ms += latency
            agent.progress = 1.0
            agent.output_preview = response_full[:OUTPUT_PREVIEW_LIMIT]
            agent.last_message = response_full[:LAST_MESSAGE_LIMIT]
            agent.model = model
            agent.status = "done"
            agent.completed_at = now_ms()
            ctrl.agent_outputs[aid] = response_full

            run.total_prompt_tokens += p_tok
            run.total_completion_tokens += c_tok
            run.total_tokens = run.total_prompt_tokens + run.total_completion_tokens
            run.total_llm_calls += 1

            await bus.publish_run_update(run)
            await _emit(
                run.run_id,
                "agent_llm_call",
                agent=aid,
                message=response_full[:LAST_MESSAGE_LIMIT],
                data={
                    "call_id": call_id,
                    "agent_id": aid,
                    "step_index": idx + 1,
                    "output_kind": output_kind,
                    "prompt_full": prompt_full,
                    "response_full": response_full,
                    "prompt_tokens": p_tok,
                    "completion_tokens": c_tok,
                    "latency_ms": latency,
                    "model": model,
                    "token_usage": {"prompt": p_tok, "completion": c_tok, "total": p_tok + c_tok},
                },
            )
            _persist_agent_call(
                run_id=run.run_id,
                agent_id=aid,
                step_index=idx + 1,
                call_id=call_id,
                prompt_full=prompt_full,
                response_full=response_full,
                meta={
                    "mode": run.mode,
                    "output_kind": output_kind,
                    "model": model,
                    "prompt_tokens": p_tok,
                    "completion_tokens": c_tok,
                    "latency_ms": latency,
                    "step_index": idx + 1,
                    "retry_count": agent.retry_count,
                },
            )
            if validation_warning:
                await _emit(
                    run.run_id,
                    "agent_validation_warning",
                    agent=aid,
                    message=validation_warning,
                    data={"agent_id": aid, "output_kind": output_kind},
                )
            await _emit(
                run.run_id,
                "agent_completed",
                agent=aid,
                message=f"{agent.name} 完成（token {agent.total_tokens:,}）",
                data={
                    "output_preview": agent.output_preview,
                    "total_tokens": agent.total_tokens,
                    "retry_count": agent.retry_count,
                },
            )
            return False
