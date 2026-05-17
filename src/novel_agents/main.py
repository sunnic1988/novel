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

    console.print("\n[bold green]项目初始化完成！[/]")
    console.print("[cyan]下一步：[/]")
    console.print("  1. 在 .env 中配置 APIMART_API_KEY（从 https://apimart.ai/keys 获取）")
    console.print("  2. 编辑 plans/synopsis.md 填写故事大纲")
    console.print("  3. 在 bible/characters/ 中添加角色卡片")
    console.print("  4. 运行 novel ingest 导入参考范文")
    console.print("  5. 运行 novel write 1 -t '第一章标题' 开始创作")


if __name__ == "__main__":
    cli()
