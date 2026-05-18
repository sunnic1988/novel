"""编排器 — 协调6个Agent的章节创作流水线"""

from __future__ import annotations

from pathlib import Path

from crewai import Crew, Process, Task
from rich.console import Console
from rich.panel import Panel

from novel_agents.agents import (
    create_planner,
    create_polisher,
    create_reader_sim,
    create_reviewer,
    create_world_builder,
    create_writer,
)
from novel_agents.core.memory import ingest_chapter, ingest_reference_texts

console = Console()
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _read_file_safe(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _load_synopsis() -> str:
    return _read_file_safe(PROJECT_ROOT / "plans" / "synopsis.md")


def _load_bible_summary() -> str:
    parts = []
    bible = PROJECT_ROOT / "bible"
    for md in sorted(bible.rglob("*.md")):
        parts.append(f"### {md.relative_to(bible)}\n{md.read_text(encoding='utf-8')[:2000]}")
    return "\n\n".join(parts) if parts else "（故事圣经为空）"


def _load_previous_chapters(up_to: int, count: int = 3) -> str:
    """分层 context — 解决长连载 token 爆炸问题。

    - 最近 count 章：完整后 3000 字（防止超长）
    - 前 10 章：每章 300 字摘要（来自 summaries/）
    - 全书伏笔账本（账本式条目）
    - 全书近 5 条读者反馈摘要
    """
    chapters_dir = PROJECT_ROOT / "chapters"
    parts: list[str] = []

    # 最近 count 章原文
    recent = []
    for i in range(max(1, up_to - count), up_to):
        ch_file = chapters_dir / f"ch{i:03d}.md"
        if ch_file.exists():
            content = ch_file.read_text(encoding="utf-8")
            recent.append(f"### 第{i}章原文（截尾 3000 字）\n{content[-3000:]}")
    if recent:
        parts.append("## 最近章节（完整片段）\n" + "\n\n".join(recent))

    # 更前面的章节摘要
    try:
        from novel_agents.book import summaries as _sums

        older_summaries = _sums.list_range(max(1, up_to - count - 10), up_to - count)
        if older_summaries:
            sm = "\n".join(f"- 第{n}章：{t}" for n, t in older_summaries)
            parts.append("## 更早章节摘要（最多 10 章）\n" + sm)
    except Exception:
        pass

    # 伏笔账本（账本式）
    try:
        from novel_agents.book import foreshadowing as _fs

        fs_items = _fs.list_items()
        if fs_items:
            lines = [f"- {it.get('id')} | {it.get('title')} | "
                     f"埋于 {it.get('planted_chapter')} 章 | "
                     f"计划回收 {it.get('planned_payoff_chapter')} 章 | "
                     f"状态 {it.get('status')}"
                     for it in fs_items]
            parts.append("## 伏笔账本（仅供参考，写作时注意呼应）\n" + "\n".join(lines))
    except Exception:
        pass

    # 近 3 条读者反馈
    try:
        from novel_agents.book import feedback as _fb

        fb_text = _fb.latest_for_planning(up_to, max_chapters=3)
        if fb_text:
            parts.append("## 近期读者反馈（反向输入到本章）\n" + fb_text)
    except Exception:
        pass

    return "\n\n".join(parts) if parts else "（无前文）"


OPENING_GUIDANCE = """
## 🚨 开篇黄金 3 章特殊要求（必读）

读者前 3 章弃书率 > 90%，本章必须满足以下任务：
1. **第 1-3 段必有钩子**：开篇即冲突/对话/异象，禁用环境铺垫开场
2. **第 1 章必现金手指**：重生记忆 / 觉醒系统 / 神秘宝物 至少亮一个（不必全开发挥）
3. **共情锚点**：主角必须有一个能让读者代入的"恨/痛/不甘"
4. **第一次小爽点**：本章末段必须有"反差/打脸/碾压/逆袭"中的至少一项
5. **悬念 3 层**：本章悬念 + 下章悬念 + 长线大悬念，各埋一个
6. **配角钩子**：至少有一个"以后还要回收"的反派/红颜
7. **章末钩子等级 S**：禁用平稳收尾，必须是"读者下一秒就想点开下一章"
"""


def _load_chapter_plan(chapter_num: int) -> str:
    plan_file = PROJECT_ROOT / "plans" / f"ch{chapter_num:03d}-plan.md"
    return _read_file_safe(plan_file)


def run_chapter_pipeline(
    chapter_num: int,
    chapter_title: str = "",
    max_review_rounds: int = 3,
    synopsis_override: str = "",
    is_opening: bool | None = None,
) -> str:
    """执行单章创作流水线"""

    msg = f"[bold cyan]开始创作第 {chapter_num} 章: {chapter_title}[/]"
    console.print(Panel(msg, expand=False))

    # 准备上下文
    ref_count = ingest_reference_texts()
    if ref_count > 0:
        console.print(f"[green]已导入 {ref_count} 个新的范文片段到向量库[/]")

    synopsis = synopsis_override or _load_synopsis()
    bible_summary = _load_bible_summary()
    prev_chapters = _load_previous_chapters(chapter_num)
    existing_plan = _load_chapter_plan(chapter_num)

    # 创建所有Agent
    planner = create_planner()
    world_builder = create_world_builder()
    writer = create_writer()
    reviewer = create_reviewer()
    polisher = create_polisher()
    reader_sim = create_reader_sim()

    # 开篇 3 章特化（自动检测或显式标记）
    if is_opening is None:
        is_opening = chapter_num <= 3
    opening_section = OPENING_GUIDANCE if is_opening else ""

    shared_context = (
        f"## 故事总纲\n{synopsis}\n\n"
        f"## 世界观设定摘要\n{bible_summary}\n\n"
        f"## 前文回顾（最近章节）\n{prev_chapters}\n\n"
        f"{opening_section}\n"
        f"## 当前章节：第{chapter_num}章 {chapter_title}"
    )

    # ── 阶段1: 策划 ──
    console.print("\n[bold yellow]▶ 阶段1：策划师制定场景规划[/]")

    plan_description = (
        f"请为第{chapter_num}章制定详细的场景规划（beats）。\n\n"
        f"{shared_context}\n\n"
    )
    if existing_plan:
        plan_description += f"## 已有规划草案（可参考或修改）\n{existing_plan}\n\n"

    plan_description += (
        "请输出以下内容：\n"
        "1. 本章核心事件（一句话）\n"
        "2. 情绪曲线设计（低→高→低→更高 等）\n"
        "3. 具体场景beats（按顺序列出每个场景的：地点、人物、事件、情绪、目的）\n"
        "4. 章末钩子设计\n"
        "5. 与前文的衔接点\n"
        "6. 本章字数目标（2000-3000字）"
    )

    plan_task = Task(
        description=plan_description,
        expected_output="包含场景beats、情绪曲线、钩子设计的完整章节规划",
        agent=planner,
    )

    # ── 阶段2: 世界观检查 ──
    console.print("[bold yellow]▶ 阶段2：世界观师检查设定一致性[/]")

    worldbuild_task = Task(
        description=(
            f"审查策划师的章节规划，确保所有设定与故事圣经一致。\n\n"
            f"{shared_context}\n\n"
            "请检查：\n"
            "1. 人物修为、性格是否与人物卡一致\n"
            "2. 法宝、术法是否符合力量体系设定\n"
            "3. 地理位置、门派关系是否准确\n"
            "4. 时间线是否合理\n"
            "5. 如有新增设定，是否与已有体系兼容\n\n"
            "输出：设定审查通过/不通过 + 需要修正的点 + 本章涉及的设定清单"
        ),
        expected_output="设定一致性审查报告，包含通过/不通过结论和修正建议",
        agent=world_builder,
        context=[plan_task],
    )

    # ── 阶段3: 写作 ──
    console.print("[bold yellow]▶ 阶段3：写手撰写章节正文[/]")

    write_task = Task(
        description=(
            f"根据策划师的场景规划和世界观师的审查意见，撰写第{chapter_num}章正文。\n\n"
            f"{shared_context}\n\n"
            "写作要求：\n"
            "1. 严格按照场景规划的beats顺序展开\n"
            "2. 遵循文风指南，杜绝AI八股词\n"
            "3. 对话要有角色辨识度\n"
            "4. 战斗场面要有策略感和视觉冲击\n"
            "5. 修炼/突破场面要有仪式感\n"
            "6. 章末必须有强力钩子\n"
            "7. 字数控制在2000-3000字\n"
            "8. 用中文写作，输出纯正文（不要元描述）\n\n"
            "重要：你已经通过上下文获得了所有需要的信息。"
            "请直接开始写作，不需要再查阅任何资料。"
            "你的输出必须是纯章节正文内容，不要包含任何思考过程或工具调用。"
        ),
        expected_output="2000-3000字的章节正文，中文，纯故事内容，不含任何元描述或工具调用格式",
        agent=writer,
        context=[plan_task, worldbuild_task],
    )

    # ── 阶段4: 审校 ──
    console.print("[bold yellow]▶ 阶段4：审校师十维度审查[/]")

    review_task = Task(
        description=(
            f"对写手产出的第{chapter_num}章进行严格审查。\n\n"
            f"{shared_context}\n\n"
            "请从以下十个维度评分（每项1-5分，满分50）：\n"
            "1. 叙事逻辑（情节是否连贯自洽）\n"
            "2. 人物一致性（言行是否符合人设）\n"
            "3. 设定连贯性（与世界观是否矛盾）\n"
            "4. 场景规划执行度（是否按beats展开）\n"
            "5. 节奏与张力（爽点是否到位）\n"
            "6. 对话质量（是否有辨识度和推动力）\n"
            "7. 描写质量（是否有画面感和沉浸感）\n"
            "8. 去AI味程度（是否存在AI八股特征）\n"
            "9. 钩子与悬念（章末是否让人想追更）\n"
            "10. 字数与信息密度（是否注水或过于压缩）\n\n"
            "输出格式：\n"
            "- 总分：XX/50\n"
            "- 各维度评分和点评\n"
            "- 具体修改建议（引用原文指出问题）\n"
            "- 结论：通过 / 需修改 / 需重写"
        ),
        expected_output="包含十维度评分、具体修改建议和结论的审查报告",
        agent=reviewer,
        context=[write_task, plan_task],
    )

    # ── 阶段5: 润色 ──
    console.print("[bold yellow]▶ 阶段5：润色师语言精修[/]")

    polish_task = Task(
        description=(
            f"对第{chapter_num}章进行语言级精修。基于审校师的意见，对章节正文进行润色。\n\n"
            "润色重点：\n"
            "1. 消除所有AI味词汇和句式（参考文风指南禁止列表）\n"
            "2. 优化句子节奏：紧张处用短句，铺垫处适当延展\n"
            "3. 打磨金句：每章至少有1-2句让人印象深刻的句子\n"
            "4. 对话精修：确保每个角色的说话方式独特\n"
            "5. 段落重组：避免超长段落，关键时刻单独成段\n"
            "6. 修正审校师指出的具体问题\n\n"
            "输出：润色后的完整章节正文（不要输出修改说明，只输出最终正文）"
        ),
        expected_output="润色后的完整章节正文，纯中文，去除所有AI痕迹",
        agent=polisher,
        context=[write_task, review_task],
    )

    # ── 阶段6: 读者模拟 ──
    console.print("[bold yellow]▶ 阶段6：读者模拟反馈[/]")

    reader_task = Task(
        description=(
            f"站在修仙网文核心读者的视角，对润色后的第{chapter_num}章给出体感报告。\n\n"
            "请回答：\n"
            "1. 【爽感评估】哪里让你兴奋？哪里觉得无聊？（用读者的口吻）\n"
            "2. 【代入感评估】能否代入主角视角？有没有出戏的地方？\n"
            "3. 【追更欲评估】看完这章想不想点下一章？为什么？\n"
            "4. 【弃书风险】有没有可能看到某段就直接弃了？\n"
            "5. 【金句/名场面】有没有值得截图分享到读者群的段落？\n"
            "6. 【总体评价】如果满分5星，给几星？一句话评价\n"
            "7. 【改进建议】如果只能改一个地方，改哪里？"
        ),
        expected_output="读者体感报告，包含爽感、代入感、追更欲评估和改进建议",
        agent=reader_sim,
        context=[polish_task],
    )

    # 组装Crew并执行
    crew = Crew(
        agents=[planner, world_builder, writer, reviewer, polisher, reader_sim],
        tasks=[plan_task, worldbuild_task, write_task, review_task, polish_task, reader_task],
        process=Process.sequential,
        verbose=True,
        max_rpm=30,
    )

    console.print("\n[bold green]🚀 开始执行创作流水线...[/]\n")
    result = crew.kickoff()

    # 保存产出物
    _save_outputs(chapter_num, chapter_title, crew, result)

    console.print(Panel(f"[bold green]✅ 第 {chapter_num} 章创作完成！[/]", expand=False))
    return str(result)


def _save_outputs(chapter_num: int, title: str, crew: Crew, result) -> None:
    """保存章节正文、审查报告和规划"""
    chapters_dir = PROJECT_ROOT / "chapters"
    reviews_dir = PROJECT_ROOT / "reviews"
    plans_dir = PROJECT_ROOT / "plans"

    chapters_dir.mkdir(parents=True, exist_ok=True)
    reviews_dir.mkdir(parents=True, exist_ok=True)
    plans_dir.mkdir(parents=True, exist_ok=True)

    # 取各Task的产出
    task_outputs = result.tasks_output if hasattr(result, "tasks_output") else []

    plan_text = str(task_outputs[0]) if len(task_outputs) > 0 else ""
    review_text = str(task_outputs[3]) if len(task_outputs) > 3 else ""
    polished_text = str(task_outputs[4]) if len(task_outputs) > 4 else ""
    reader_feedback = str(task_outputs[5]) if len(task_outputs) > 5 else ""

    final_text = polished_text or str(result)

    # 保存章节正文
    ch_header = f"# 第{chapter_num}章 {title}\n\n" if title else f"# 第{chapter_num}章\n\n"
    ch_path = chapters_dir / f"ch{chapter_num:03d}.md"
    ch_path.write_text(ch_header + final_text, encoding="utf-8")
    console.print(f"[green]  📖 章节正文已保存: {ch_path}[/]")

    # 保存规划
    plan_path = plans_dir / f"ch{chapter_num:03d}-plan.md"
    plan_path.write_text(f"# 第{chapter_num}章 场景规划\n\n{plan_text}", encoding="utf-8")
    console.print(f"[green]  📋 场景规划已保存: {plan_path}[/]")

    # 保存审查报告
    review_path = reviews_dir / f"ch{chapter_num:03d}-review.md"
    full_review = (
        f"# 第{chapter_num}章 审查报告\n\n{review_text}"
        f"\n\n---\n\n## 读者反馈\n\n{reader_feedback}"
    )
    review_path.write_text(full_review, encoding="utf-8")
    console.print(f"[green]  📝 审查报告已保存: {review_path}[/]")

    # 向量化已写章节
    ingest_chapter(chapter_num, final_text)
    console.print("[green]  🔍 章节已向量化入库[/]")

    # 章节副产物入账（live 模式下也产出，但 KPI 字段为粗估）
    try:
        from novel_agents.book import (
            ai_taste,
        )
        from novel_agents.book import (
            kpi as kpi_mod,
        )
        from novel_agents.book import (
            summaries as sum_mod,
        )

        # 章节摘要（规则法兜底；live 模式后续可由独立摘要 Agent 替换）
        summary_text = sum_mod.auto_summarize(final_text)
        sum_mod.save(chapter_num, summary_text)

        # AI 味硬检测
        lint = ai_taste.analyze(final_text)
        import json as _json

        from novel_agents.book.paths import ai_lint_path

        ai_lint_path(chapter_num).write_text(
            _json.dumps(lint.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # KPI（基于 reviewer 文本启发式提取；后续可被结构化 LLM 替换）
        word_count = sum(1 for c in final_text if "\u4e00" <= c <= "\u9fff")
        kpi_obj = kpi_mod.ChapterKPI(
            chapter=chapter_num,
            title=title,
            word_count=word_count,
            ai_taste_score=lint.score,
            # 粗略评分占位 — 实际 reviewer 应输出结构化 JSON
            overall_score=0.7,
        )
        kpi_mod.save(kpi_obj)
        console.print("[green]  📊 KPI / 摘要 / AI 味 lint 已入账[/]")
    except Exception as exc:
        console.print(f"[yellow]  ⚠ 账本写入失败: {exc}[/]")
