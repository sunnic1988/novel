"""Run 生命周期管理 — 启动 / 暂停 / 干预 / 终止 6 Agent 流水线"""

from __future__ import annotations

import asyncio
import os
import random
import uuid
from typing import Any

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

# 模拟模式下每个 Agent 输出的样本片段（与系统中真实的 6 个 Agent 职责一一对应）
MOCK_OUTPUTS: dict[str, list[str]] = {
    "planner": [
        "本章核心事件：少年陈尘在乱葬岗目睹师兄陨落，意外得到一枚残破玉简。",
        "情绪曲线设计：压抑（蹲守）→ 紧张（追杀）→ 暴怒（师兄陨落）→ 破釜沉舟。",
        (
            "Beats: 1) 黄昏乱葬岗蹲守; 2) 师兄重伤逃来; 3) 黑袍人追至; "
            "4) 师兄交付玉简; 5) 少年怒夺玉简; 6) 玉简共鸣识主。"
        ),
        "钩子：玉简中传来一道沙哑笑声——'小子，可愿拜我为师？'",
    ],
    "world_builder": [
        "审查结论：通过。新增设定『玄阴玉简』与既有功法体系兼容。",
        "本章涉及设定：练气七层（陈尘）/ 筑基中期（黑袍）/ 玉简属性偏阴煞。",
        "时间线：故事时间第 137 日傍晚，与前文衔接处无冲突。",
        "建议：黑袍人法器『噬魂幡』需补一句在第 5 章已出现的伏笔回扣。",
    ],
    "writer": [
        "暮色像一摊洗不开的旧墨，沿着乱葬岗的碎石缓缓铺陈。陈尘屏住呼吸，藏在一座坍塌的衣冠冢后。",
        "他能闻到风里有铁锈味——是血。师兄的血。",
        "黑袍人的脚步停在三丈外，'交出来，留你全尸。'",
        "陈尘忽然笑了。笑里有泪，也有别的什么——比泪更烫的东西。",
        "他从怀里掏出那枚玉简，玉简表面骤然浮起一行字：『小子，可愿拜我为师？』",
    ],
    "reviewer": [
        "总分：43/50",
        "叙事逻辑 5/5 · 人物一致性 5/5 · 设定连贯 4/5 · 场景执行 5/5 · 节奏 4/5",
        "对话质量 4/5 · 描写质量 5/5 · 去AI味 4/5 · 钩子 5/5 · 信息密度 4/5",
        (
            "可优化：第 3 个场景中『噬魂幡』描写略平，建议加 1-2 句声效或寒意；"
            "段末『比泪更烫的东西』节奏可再短一拍。"
        ),
        "结论：通过（建议轻度润色）。",
    ],
    "polisher": [
        "暮色是化不开的旧墨，一寸寸漫过乱葬岗的碎骨。",
        "陈尘伏在塌掉一半的衣冠冢后，连呼吸都收得极薄。",
        "风里有血腥味。是师兄的。",
        "脚步在三丈外停住。",
        "『交出来——留你全尸。』",
        "陈尘忽然笑了。笑里有泪。也有别的，比泪更烫的东西。",
        "他摸出那枚玉简。玉面骤然浮起一行字：",
        "『小子，可愿拜我为师？』",
    ],
    "reader_sim": [
        "爽感评估：师兄死的那段我血压上来了，太憋屈了——这才对。",
        "代入感：『比泪更烫的东西』那一句直接破防，给评论区直接送神图素材。",
        "追更欲：必追。玉简识主+老怪物收徒，下章不开都说不过去。",
        "弃书风险：低。前 200 字差点没耐心，希望开头能再快一点。",
        "评分：4.5/5 ⭐",
        "改进建议：开头黄昏铺垫压缩到 80 字内，把『血腥味』那一句提前。",
    ],
}


class RunController:
    """单个 run 的生命周期控制器"""

    def __init__(self, run: RunSummary) -> None:
        self.run = run
        self.pause_event = asyncio.Event()
        self.pause_event.set()  # 默认非暂停
        self.abort_event = asyncio.Event()
        self.intervention_outputs: dict[str, str] = {}
        self.intervention_waiters: dict[str, asyncio.Event] = {}
        self.task: asyncio.Task[Any] | None = None

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
        ctrl.intervention_outputs[agent_id] = edited_output
        waiter = ctrl.intervention_waiters.get(agent_id)
        if waiter:
            if resume:
                waiter.set()
        await bus.publish(
            Event(
                run_id=run_id,
                type="intervention_applied",
                agent=agent_id,
                message=f"人工干预已应用 ({len(edited_output)} 字)",
                data={"edited_output_preview": edited_output[:200]},
            )
        )
        # Update agent state
        for a in ctrl.run.agents:
            if a.id == agent_id:
                a.output_preview = edited_output[:600]
                a.status = "done" if resume else "awaiting_intervention"
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


# 各 Agent 在模拟模式下的执行步长（步数 + 每步延迟范围）
MOCK_STEPS: dict[str, tuple[int, tuple[float, float]]] = {
    "planner": (5, (0.35, 0.7)),
    "world_builder": (4, (0.3, 0.6)),
    "writer": (8, (0.5, 1.1)),
    "reviewer": (5, (0.35, 0.7)),
    "polisher": (7, (0.4, 0.9)),
    "reader_sim": (4, (0.3, 0.55)),
}


async def _run_pipeline(ctrl: RunController, req: StartRunRequest) -> None:
    run = ctrl.run
    run.status = "running"
    run.started_at = now_ms()
    await bus.publish_run_update(run)
    await _emit(
        run.run_id,
        "run_started",
        message=(
            f"开始创作第 {run.chapter_num} 章 "
            f"「{run.chapter_title or '未命名'}」 (mode={run.mode})"
        ),
        data={"chapter_num": run.chapter_num, "title": run.chapter_title, "mode": run.mode},
    )

    try:
        if run.mode == "live":
            ok = await _run_live(ctrl, req)
            if not ok:
                return
        else:
            await _run_mock(ctrl)

        if ctrl.abort_event.is_set():
            return

        run.status = "completed"
        run.completed_at = now_ms()
        await bus.publish_run_update(run)
        await _emit(
            run.run_id,
            "run_completed",
            message=(
                f"流水线完成，总 token: {run.total_tokens:,}"
                f"（输入 {run.total_prompt_tokens:,} / 输出 {run.total_completion_tokens:,}）"
            ),
            data={
                "total_tokens": run.total_tokens,
                "prompt_tokens": run.total_prompt_tokens,
                "completion_tokens": run.total_completion_tokens,
            },
        )
    except asyncio.CancelledError:
        run.status = "aborted"
        await bus.publish_run_update(run)
        raise
    except Exception as exc:  # pragma: no cover - defensive
        run.status = "error"
        await bus.publish_run_update(run)
        await _emit(run.run_id, "run_error", message=f"流水线异常: {exc}")


async def _run_mock(ctrl: RunController) -> None:
    run = ctrl.run

    for idx, aid in enumerate(AGENT_ORDER):
        if ctrl.abort_event.is_set():
            return
        agent = _find_agent(run, aid)
        await _execute_mock_agent(ctrl, agent, idx)
        if ctrl.abort_event.is_set():
            return
        # 非 auto_run 模式或 Writer/Polisher 关键节点，等待干预
        if not run.auto_run and aid in ("writer", "polisher"):
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

    steps, (lo, hi) = MOCK_STEPS[agent.id]
    outputs = MOCK_OUTPUTS[agent.id]

    # 若该 Agent 可以调用爆款范文，模拟一次工具调用
    if agent.uses_references:
        await asyncio.sleep(random.uniform(0.2, 0.5))
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
    for step in range(steps):
        if ctrl.abort_event.is_set():
            return
        await ctrl.wait_if_paused()
        await asyncio.sleep(random.uniform(lo, hi))
        chunk = outputs[step % len(outputs)]
        accumulated_chunks.append(chunk)
        # 模拟 token 消耗
        p_tok = random.randint(180, 380)
        c_tok = random.randint(120, 360)
        latency = int(random.uniform(lo, hi) * 1000)
        agent.prompt_tokens += p_tok
        agent.completion_tokens += c_tok
        agent.total_tokens = agent.prompt_tokens + agent.completion_tokens
        agent.llm_calls += 1
        agent.latency_ms += latency
        agent.progress = (step + 1) / steps
        agent.last_message = chunk[:80]
        agent.output_preview = "\n".join(accumulated_chunks)[:1200]

        run.total_prompt_tokens += p_tok
        run.total_completion_tokens += c_tok
        run.total_tokens = run.total_prompt_tokens + run.total_completion_tokens
        run.total_llm_calls += 1

        await bus.publish_run_update(run)
        await _emit(
            run.run_id,
            "agent_llm_call",
            agent=agent.id,
            message=chunk,
            data={
                "step": step + 1,
                "total_steps": steps,
                "prompt_tokens": p_tok,
                "completion_tokens": c_tok,
                "latency_ms": latency,
                "model": agent.model,
            },
        )

    agent.status = "done"
    agent.completed_at = now_ms()
    agent.progress = 1.0
    agent.last_message = "✓ 完成"
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
    """在 auto_run=False 模式下等待人工干预"""
    run = ctrl.run
    agent.status = "awaiting_intervention"
    run.status = "paused"
    run.paused_at_agent = agent.id
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
    run.paused_at_agent = None
    ctrl.intervention_waiters.pop(agent.id, None)
    ctrl.pause_event.set()
    run.status = "running"
    await bus.publish_run_update(run)


async def _run_live(ctrl: RunController, req: StartRunRequest) -> bool:
    """真实模式 — 调用 orchestrator。当前实现为在线程池中跑同步管线，
    并通过 wrapper 收集 token 用量。任务级中间结果会在 task 结束时透传到事件总线。
    """
    run = ctrl.run

    if not os.getenv("APIMART_API_KEY"):
        await _emit(
            run.run_id,
            "run_error",
            message="未设置 APIMART_API_KEY；自动切换为 mock 演示模式。",
        )
        run.mode = "mock"
        await bus.publish_run_update(run)
        await _run_mock(ctrl)
        return True

    # Live 模式：在线程中执行 orchestrator.run_chapter_pipeline，但在执行前
    # 注入一个事件回调，让我们可以在每个 Task 完成时发出 agent_completed 事件。
    try:
        from novel_agents.core import orchestrator as orch
    except Exception as exc:
        await _emit(run.run_id, "run_error", message=f"无法导入 orchestrator: {exc}")
        return False

    loop = asyncio.get_running_loop()

    def emit_sync(type_: str, agent: str | None, message: str, data: dict[str, Any] | None = None):
        asyncio.run_coroutine_threadsafe(
            _emit(run.run_id, type_, agent=agent, message=message, data=data or {}),
            loop,
        )

    def update_sync():
        asyncio.run_coroutine_threadsafe(bus.publish_run_update(run), loop)

    # 在 thread 内执行，简化处理；live 模式下我们仍然给前端发送进度心跳
    def thread_target() -> str:
        # 在每个 agent 启动时手动 emit；CrewAI 的细粒度回调因版本差异较大，
        # 这里采用粗粒度（任务级）事件。
        for aid in AGENT_ORDER:
            agent = _find_agent(run, aid)
            agent.status = "running"
            agent.started_at = now_ms()
            emit_sync("agent_started", aid, f"{agent.name} 开始工作")
            update_sync()
        try:
            result = orch.run_chapter_pipeline(
                req.chapter_num,
                req.chapter_title,
                3,
                synopsis_override=req.synopsis_override,
            )
        except Exception as exc:
            emit_sync("run_error", None, f"管线执行失败: {exc}")
            return ""

        for aid in AGENT_ORDER:
            agent = _find_agent(run, aid)
            agent.status = "done"
            agent.completed_at = now_ms()
            emit_sync("agent_completed", aid, f"{agent.name} 完成")
            update_sync()
        return str(result)

    await asyncio.to_thread(thread_target)
    return True
