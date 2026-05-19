"""CLI入口 — 玄幻修仙多Agent创作系统"""

from __future__ import annotations

from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

load_dotenv()

console = Console()
PROJECT_ROOT = Path(__file__).resolve().parents[2]


@click.group()
def cli():
    """🏔️ 玄幻修仙多Agent创作系统"""
    pass


@cli.command()
@click.argument("chapter_num", type=int)
@click.option("--title", "-t", default="", help="章节标题")
@click.option("--max-rounds", "-r", default=3, help="最大审校轮次")
def write(chapter_num: int, title: str, max_rounds: int):
    """创作指定章节（触发完整流水线）"""
    from novel_agents.core.orchestrator import run_chapter_pipeline

    console.print(Panel("[bold cyan]🏔️ 玄幻修仙多Agent创作系统启动[/]", expand=False))
    run_chapter_pipeline(chapter_num, title, max_rounds)
    console.print("\n[bold green]创作完成！[/]")


@cli.command()
@click.option("--start", "-s", type=int, required=True, help="起始章节号")
@click.option("--end", "-e", type=int, required=True, help="结束章节号")
def batch(start: int, end: int):
    """批量创作多个章节"""
    from novel_agents.core.orchestrator import run_chapter_pipeline

    console.print(Panel(f"[bold cyan]📚 批量创作: 第{start}章 ~ 第{end}章[/]", expand=False))
    for ch in range(start, end + 1):
        try:
            run_chapter_pipeline(ch)
        except Exception as e:
            console.print(f"[red]❌ 第{ch}章创作失败: {e}[/]")
            if not click.confirm("是否继续下一章？"):
                break


@cli.command()
def ingest():
    """导入爆款范文到向量库"""
    from novel_agents.core.memory import ingest_reference_texts

    console.print("[cyan]正在导入范文...[/]")
    count = ingest_reference_texts()
    console.print(f"[green]✅ 已导入 {count} 个新片段到向量库[/]")


@cli.command()
@click.argument("query")
@click.option("--n", "-n", default=5, help="返回结果数")
def search(query: str, n: int):
    """搜索爆款范文库"""
    from novel_agents.core.memory import query_references

    results = query_references(query, n)
    if not results:
        console.print("[yellow]未找到相关范文片段。请先运行 novel ingest 导入范文。[/]")
        return
    for i, text in enumerate(results, 1):
        console.print(Panel(text, title=f"片段 {i}", border_style="blue"))


@cli.command()
def status():
    """查看项目状态"""
    table = Table(title="📊 项目状态")
    table.add_column("类别", style="cyan")
    table.add_column("数量/状态", style="green")

    # 统计章节
    chapters_dir = PROJECT_ROOT / "chapters"
    ch_count = len(list(chapters_dir.glob("ch*.md"))) if chapters_dir.exists() else 0
    table.add_row("已完成章节", str(ch_count))

    # 统计人物卡
    chars_dir = PROJECT_ROOT / "bible" / "characters"
    char_count = len(list(chars_dir.glob("*.md"))) if chars_dir.exists() else 0
    table.add_row("人物卡片", str(char_count))

    # 统计范文
    refs_dir = PROJECT_ROOT / "references"
    ref_count = (
        len(list(refs_dir.glob("*.md"))) + len(list(refs_dir.glob("*.txt")))
        if refs_dir.exists()
        else 0
    )
    table.add_row("参考范文", str(ref_count))

    # 检查大纲
    synopsis = PROJECT_ROOT / "plans" / "synopsis.md"
    table.add_row("故事大纲", "✅ 已创建" if synopsis.exists() else "❌ 未创建")

    # 检查LLM配置
    import os

    has_apimart = bool(os.getenv("APIMART_API_KEY"))
    table.add_row("APIMart API", "✅ 已配置" if has_apimart else "⚠️ 未配置")

    console.print(table)

    # 向量库状态
    try:
        from novel_agents.core.memory import get_chapters_collection, get_reference_collection

        ref_col = get_reference_collection()
        ch_col = get_chapters_collection()
        ref_n, ch_n = ref_col.count(), ch_col.count()
        console.print(f"\n[cyan]向量库:[/] 范文片段 {ref_n} 条 | 章节片段 {ch_n} 条")
    except Exception:
        console.print("\n[yellow]向量库未初始化[/]")


@cli.command()
@click.option("--host", default="127.0.0.1", help="监听地址")
@click.option("--port", "-p", default=8765, type=int, help="监听端口")
@click.option("--reload", is_flag=True, help="代码改动时自动重载")
def serve(host: str, port: int, reload: bool):
    """启动仪表盘后端 API（FastAPI + WebSocket）"""
    import uvicorn

    banner = f"[bold cyan]🚀 启动 Agent 仪表盘 API[/]\n→ http://{host}:{port}"
    console.print(Panel(banner, expand=False))
    if reload:
        uvicorn.run(
            "novel_agents.server.app:create_app",
            host=host,
            port=port,
            reload=True,
            factory=True,
        )
    else:
        from novel_agents.server.app import create_app

        uvicorn.run(create_app(), host=host, port=port)


def _write_if_missing(path: Path, content: str) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")
    return True


def _init_template_files() -> list[str]:
    created: list[str] = []
    templates: dict[str, str] = {
        "bible/style_guide.md": """# 文风指南

## 禁止 AI 八股

- 禁止滥用：然而、与此同时、事实上、总之、不禁、缓缓、微微
- 禁止空洞升华：「他意识到」「这意味着」「这一刻他明白了」
- 禁止形容词堆砌，优先精准动词

## 节奏

- Show, don't tell
- 对话推动情节，少用大段心理独白代替行动
""",
        "bible/power_system.md": """# 力量体系

## 境界（由低到高）

1. **练气期**（一至九层）— 引气入体
2. **筑基期** — 筑就道基
3. **金丹期** — 凝结金丹
4. **元婴期** — 元婴出窍
5. **化神期** — 神识化形

## 战力原则

- 越级战斗需有代价或金手指支撑
- 突破名场面要详写，日常修炼可略写
""",
        "bible/characters/主角模板.md": """# 主角人物卡

- **姓名**：陈尘（可改）
- **身份**：宗门杂役 / 外门弟子
- **当前境界**：练气三层
- **性格**：隐忍、记仇、谋定后动
- **核心动机**：为师兄复仇 / 重回巅峰
- **金手指**：（待填）
- **说话方式**：少言、短句，危机时反而更冷静
""",
        "plans/synopsis.md": """# 故事大纲

## 一句话梗概

（例：重生剑帝回到十六岁杂役之身，从被瞧不起开始杀回血衣楼。）

## 第一卷目标

- 第 1–3 章：开篇钩子 + 金手指亮相
- 第 4–10 章：（待填）

## 主要矛盾

- 外部：血衣楼 / 宗门压迫
- 内部：复仇与隐忍的拉扯
""",
    }
    for rel, text in templates.items():
        path = PROJECT_ROOT / rel
        if _write_if_missing(path, text):
            created.append(rel)
    return created


@cli.command()
def init():
    """初始化项目（创建必要目录和模板文件）"""
    dirs = [
        "bible/characters",
        "bible/worldview",
        "plans/volumes",
        "chapters",
        "reviews",
        "facts",
        "references",
        "output",
    ]
    for d in dirs:
        p = PROJECT_ROOT / d
        p.mkdir(parents=True, exist_ok=True)
        console.print(f"[green]  ✅ {d}/[/]")

    for rel in _init_template_files():
        console.print(f"[green]  ✅ {rel}[/]")

    console.print("\n[bold green]项目初始化完成！[/]")
    console.print("[cyan]下一步：[/]")
    console.print("  1. 在 .env 中配置 APIMART_API_KEY（从 https://apimart.ai/keys 获取）")
    console.print("  2. 编辑 plans/synopsis.md 填写故事大纲")
    console.print("  3. 在 bible/characters/ 中完善角色卡片")
    console.print("  4. 运行 novel ingest 导入参考范文")
    console.print("  5. 运行 novel write 1 -t '第一章标题' 开始创作，或 python start.py 打开仪表盘")


if __name__ == "__main__":
    cli()
