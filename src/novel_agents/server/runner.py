"""Run 生命周期管理 — 启动 / 暂停 / 干预 / 终止 9 Agent 流水线

Mock 模式下每轮 run 会同步生成一份完整的「章节副产物包」：
KPI / 标题 / 金句 / 伏笔变动 / 角色 runtime / AI 味 lint / 章节摘要 / 简介候选 / 成本估算。
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
    character_runtime,
    feedback,
    foreshadowing,
    highlights,
    summaries,
)
from novel_agents.book import (
    cost as cost_mod,
)
from novel_agents.book import (
    kpi as kpi_mod,
)
from novel_agents.book import (
    titles as titles_mod,
)
from novel_agents.book.ai_taste import analyze as ai_taste_analyze
from novel_agents.book.paths import ai_lint_path, ensure_dirs
from novel_agents.server.events import bus
from novel_agents.server.mock_data import (
    MOCK_AI_LINT_SAMPLE,
    MOCK_CHARACTER_UPDATES,
    MOCK_FORESHADOWING_PLANTS,
    MOCK_HIGHLIGHTS,
    MOCK_OUTPUTS,
    MOCK_STEPS,
    MOCK_SUMMARY,
    MOCK_SYNOPSIS_CANDIDATES,
    MOCK_TITLE_CANDIDATES,
    randomize_kpi,
)
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


class RunController:
    """单个 run 的生命周期控制器"""

    def __init__(self, run: RunSummary) -> None:
        self.run = run
        self.pause_event = asyncio.Event()
        self.pause_event.set()
        self.abort_event = asyncio.Event()
        self.intervention_outputs: dict[str, str] = {}
        self.intervention_waiters: dict[str, asyncio.Event] = {}
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
            chapter_num=req.chapter_num,
            chapter_title=req.chapter_title,
            mode=req.mode,
            auto_run=req.auto_run,
            status="queued",
            agents=agents,
        )
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
            f"(mode={run.mode}, is_opening={ctrl.is_opening}, best_of_n={ctrl.best_of_n}, "
            f"step_confirm={ctrl.step_confirm_mode})"
        ),
        data={
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
        if run.mode == "live":
            ok = await _run_live(ctrl, req)
            if not ok:
                run.status = "error"
                _write_run_state(run)
                await bus.publish_run_update(run)
                return
        else:
            await _run_mock(ctrl)

        if ctrl.abort_event.is_set():
            return

        # 章节副产物入账（mock / live 均执行；live 下 KPI 由 reviewer 给）
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


async def _run_mock(ctrl: RunController) -> None:
    run = ctrl.run

    for idx, aid in enumerate(AGENT_ORDER):
        if ctrl.abort_event.is_set():
            return
        agent = _find_agent(run, aid)
        if aid not in ctrl.enabled_agents:
            await _emit(
                run.run_id, "agent_skipped", agent=aid, message=f"{agent.name} 已禁用，跳过"
            )
            continue
        await _execute_mock_agent(ctrl, agent, idx)
        if ctrl.abort_event.is_set():
            return
        if ctrl.step_confirm_mode:
            await _await_intervention(ctrl, agent)


async def _execute_mock_agent(
    ctrl: RunController, agent: AgentStatus, idx: int
) -> None:
    run = ctrl.run
    agent.status = "running"
    agent.started_at = now_ms()
    agent.progress = 0.0
    agent.last_message = "启动中…"
    await bus.publish_run_update(run)
    await _emit(
        run.run_id,
        "agent_started",
        agent=agent.id,
        message=f"{agent.name} 开始工作 · 使用模型 {agent.model}",
        data={"model": agent.model, "uses_references": agent.uses_references},
    )

    steps, (lo, hi) = MOCK_STEPS.get(agent.id, (4, (0.3, 0.7)))
    outputs = MOCK_OUTPUTS.get(agent.id, [f"{agent.name} 正在工作…"])

    if agent.uses_references:
        await asyncio.sleep(random.uniform(0.2, 0.4))
        await ctrl.wait_if_paused()
        agent.tool_calls += 1
        agent.last_message = "🔍 调用爆款范文检索…"
        await bus.publish_run_update(run)
        await _emit(
            run.run_id,
            "agent_tool_call",
            agent=agent.id,
            message="调用工具：爆款范文检索",
            data={"tool": "ReferenceSearchTool", "query": f"第{run.chapter_num}章 关键场景"},
        )

    accumulated_chunks: list[str] = []
    # 开篇 3 章特殊处理：strict pacing 警告
    if ctrl.is_opening and agent.id == "pacing_doctor":
        await _emit(
            run.run_id,
            "agent_thinking",
            agent=agent.id,
            message="🚨 开篇 3 章特化：必须在前 800 字完成金手指亮相 + 角色钩子。",
        )
    # writer best_of_n
    if agent.id == "writer" and ctrl.best_of_n > 1:
        await _emit(
            run.run_id,
            "agent_thinking",
            agent=agent.id,
            message=f"⚙ Best-of-{ctrl.best_of_n} 并行试写中（mock 下汇总最佳版本）",
            data={"best_of_n": ctrl.best_of_n},
        )

    for step in range(steps):
        if ctrl.abort_event.is_set():
            return
        await ctrl.wait_if_paused()
        await asyncio.sleep(random.uniform(lo, hi))
        chunk = outputs[step % len(outputs)]
        accumulated_chunks.append(chunk)
        p_tok = random.randint(180, 380)
        c_tok = random.randint(120, 360)
        if agent.id == "writer" and ctrl.best_of_n > 1:
            p_tok *= ctrl.best_of_n
            c_tok *= ctrl.best_of_n
        latency = int(random.uniform(lo, hi) * 1000)
        agent.prompt_tokens += p_tok
        agent.completion_tokens += c_tok
        agent.total_tokens = agent.prompt_tokens + agent.completion_tokens
        agent.llm_calls += 1
        agent.latency_ms += latency
        agent.progress = (step + 1) / steps
        agent.last_message = chunk[:80]
        agent.output_preview = "\n".join(accumulated_chunks)[:OUTPUT_PREVIEW_LIMIT]

        run.total_prompt_tokens += p_tok
        run.total_completion_tokens += c_tok
        run.total_tokens = run.total_prompt_tokens + run.total_completion_tokens
        run.total_llm_calls += 1

        ctrl.call_index += 1
        call_id = f"{run.run_id}-{agent.id}-{ctrl.call_index}"
        prompt_full = (
            f"[MOCK] agent={agent.id}, step={step + 1}/{steps}, "
            f"chapter={run.chapter_num}, title={run.chapter_title or '未命名'}\n"
            "请基于当前上下文生成该步骤输出。"
        )
        response_full = chunk
        _persist_agent_call(
            run_id=run.run_id,
            agent_id=agent.id,
            step_index=idx + 1,
            call_id=call_id,
            prompt_full=prompt_full,
            response_full=response_full,
            meta={
                "mode": run.mode,
                "model": agent.model,
                "prompt_tokens": p_tok,
                "completion_tokens": c_tok,
                "latency_ms": latency,
                "step": step + 1,
                "total_steps": steps,
            },
        )
        await bus.publish_run_update(run)
        await _emit(
            run.run_id,
            "agent_llm_call",
            agent=agent.id,
            message=chunk,
            data={
                "call_id": call_id,
                "agent_id": agent.id,
                "step_index": step + 1,
                "step": step + 1,
                "total_steps": steps,
                "prompt_full": prompt_full,
                "response_full": response_full,
                "prompt_tokens": p_tok,
                "completion_tokens": c_tok,
                "latency_ms": latency,
                "model": agent.model,
                "token_usage": {"prompt": p_tok, "completion": c_tok, "total": p_tok + c_tok},
            },
        )

    agent.status = "done"
    agent.completed_at = now_ms()
    agent.progress = 1.0
    agent.last_message = "✓ 完成"
    ctrl.agent_outputs[agent.id] = agent.output_preview
    await bus.publish_run_update(run)
    await _emit(
        run.run_id,
        "agent_completed",
        agent=agent.id,
        message=(
            f"{agent.name} 完成（用时 "
            f"{(agent.completed_at - (agent.started_at or 0)) / 1000:.1f}s, "
            f"token {agent.total_tokens:,}）"
        ),
        data={
            "output_preview": agent.output_preview,
            "total_tokens": agent.total_tokens,
        },
    )


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


async def _persist_chapter_artifacts(ctrl: RunController) -> None:
    """章节完成后写入：摘要 / KPI / 标题 / 金句 / 伏笔变动 / 角色 runtime / AI 味 lint"""
    run = ctrl.run
    n = run.chapter_num
    ensure_dirs()

    # 1. 章节摘要
    summary_text = MOCK_SUMMARY
    summaries.save(n, summary_text)
    await _emit(
        run.run_id,
        "artifact_saved",
        agent=None,
        message=f"📝 章节摘要已保存 (summaries/ch{n:03d}.md)",
        data={"kind": "summary", "chars": len(summary_text)},
    )

    # 2. KPI（mock 自动浮动；live 模式由 reviewer 给出）
    k = randomize_kpi(n)
    kpi_obj = kpi_mod.ChapterKPI(
        chapter=n,
        title=run.chapter_title,
        word_count=2500 + random.randint(-200, 400),
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

    # 3. AI 味硬检测（基于 mock 文本运行真实算法）
    polished_text = "\n".join(MOCK_OUTPUTS["polisher"])
    try:
        lint = ai_taste_analyze(polished_text)
        lint_dict = lint.to_dict()
    except Exception:
        lint_dict = MOCK_AI_LINT_SAMPLE
    import json as _json
    ai_lint_path(n).write_text(
        _json.dumps(lint_dict, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    await _emit(
        run.run_id,
        "artifact_saved",
        message=f"🔍 AI 味检测：score={lint_dict['score']} / {lint_dict.get('level','—')}",
        data={"kind": "ai_lint", **lint_dict},
    )

    # 4. 金句库
    for line in MOCK_HIGHLIGHTS:
        highlights.add(n, line, tag="情绪", score=4.5)
    await _emit(
        run.run_id,
        "artifact_saved",
        message=f"✨ 已沉淀 {len(MOCK_HIGHLIGHTS)} 句金句入金句库",
        data={"kind": "highlights", "count": len(MOCK_HIGHLIGHTS)},
    )

    # 5. 标题候选
    titles_mod.save_titles(n, MOCK_TITLE_CANDIDATES)
    await _emit(
        run.run_id,
        "artifact_saved",
        message=f"🎯 已生成 {len(MOCK_TITLE_CANDIDATES)} 个标题候选",
        data={"kind": "titles", "candidates": MOCK_TITLE_CANDIDATES},
    )

    # 6. 简介迭代候选
    syn_text = "# 书籍简介候选\n\n" + "\n\n---\n\n".join(
        f"## 候选 {i + 1}\n{t}" for i, t in enumerate(MOCK_SYNOPSIS_CANDIDATES)
    )
    titles_mod.save_synopsis(syn_text)
    await _emit(
        run.run_id,
        "artifact_saved",
        message=f"📖 书籍简介已迭代为 {len(MOCK_SYNOPSIS_CANDIDATES)} 个候选",
        data={"kind": "synopsis_candidates", "count": len(MOCK_SYNOPSIS_CANDIDATES)},
    )

    # 7. 伏笔账本变动（章节号映射）
    for item in MOCK_FORESHADOWING_PLANTS:
        clone = dict(item)
        # 调整 planted/planned 章节号相对当前章节
        clone["planted_chapter"] = n
        if isinstance(clone.get("planned_payoff_chapter"), int):
            clone["planned_payoff_chapter"] = n + (
                clone["planned_payoff_chapter"] - 1
            )
        foreshadowing.upsert(clone)
    fs_stat = foreshadowing.stats(current_chapter=n)
    await _emit(
        run.run_id,
        "artifact_saved",
        message=(
            f"📌 伏笔账本更新：累计 {fs_stat['total']} 个，"
            f"未回收 {fs_stat['open']}，逾期 {fs_stat['overdue']}"
        ),
        data={"kind": "foreshadowing", **fs_stat},
    )

    # 8. 角色 runtime 更新
    for upd in MOCK_CHARACTER_UPDATES:
        character_runtime.append_snapshot(upd["name"], n, upd["snapshot"])
    await _emit(
        run.run_id,
        "artifact_saved",
        message=(
            f"🪄 已更新 {len(MOCK_CHARACTER_UPDATES)} 个角色的 runtime 状态"
        ),
        data={"kind": "character_runtime", "count": len(MOCK_CHARACTER_UPDATES)},
    )

    # 9. 章末读者反馈占位（用户可以从 UI 输入）
    if not feedback.load(n):
        feedback.save(
            n,
            "（这里输入读者评论摘要，会反向喂给下一章规划。Mock 模式自动留空。）",
        )


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
        await _execute_live_agent(ctrl, req, orch, agent, idx)
        if ctrl.abort_event.is_set():
            return False
        if ctrl.step_confirm_mode:
            await _await_intervention(ctrl, agent)
    return True


async def _execute_live_agent(
    ctrl: RunController,
    req: StartRunRequest,
    orch: Any,
    agent: AgentStatus,
    idx: int,
) -> None:
    run = ctrl.run
    aid = agent.id
    loop = asyncio.get_running_loop()
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

    agent.status = "running"
    agent.started_at = now_ms()
    agent.progress = 0.0
    agent.last_message = "正在生成中…"
    await bus.publish_run_update(run)
    await _emit(
        run.run_id,
        "agent_started",
        agent=aid,
        message=f"{agent.name} 开始工作 · 使用模型 {agent.model}",
        data={"model": agent.model, "uses_references": agent.uses_references, "order": idx + 1},
    )

    if agent.uses_references:
        agent.tool_calls += 1
        await _emit(
            run.run_id,
            "agent_tool_call",
            agent=aid,
            message="调用工具：爆款范文检索",
            data={"tool": "ReferenceSearchTool", "query": f"第{run.chapter_num}章 场景推进"},
        )

    try:
        result = await asyncio.to_thread(
            orch.run_single_agent_step,
            aid,
            req.chapter_num,
            req.chapter_title,
            req.synopsis_override,
            dict(ctrl.agent_outputs),
            ctrl.is_opening,
            _stream_callback,
        )
    except Exception as exc:
        agent.status = "error"
        agent.last_message = f"异常: {exc}"
        await bus.publish_run_update(run)
        await _emit(run.run_id, "run_error", agent=aid, message=f"{agent.name} 执行失败: {exc}")
        raise

    prompt_full = str(result.get("prompt_full", ""))
    response_full = str(result.get("response_full", ""))
    p_tok = int(result.get("prompt_tokens", 0))
    c_tok = int(result.get("completion_tokens", 0))
    latency = int(result.get("latency_ms", 0))
    model = str(result.get("model", agent.model))

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
            "model": model,
            "prompt_tokens": p_tok,
            "completion_tokens": c_tok,
            "latency_ms": latency,
            "step_index": idx + 1,
        },
    )
    await _emit(
        run.run_id,
        "agent_completed",
        agent=aid,
        message=f"{agent.name} 完成（token {agent.total_tokens:,}）",
        data={"output_preview": agent.output_preview, "total_tokens": agent.total_tokens},
    )
