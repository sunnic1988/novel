"""故事圣经读取工具 — 读取人物卡、世界观、力量体系等设定"""

from crewai.tools import BaseTool

from novel_agents.book.paths import bible_dir


class BibleReaderTool(BaseTool):
    name: str = "故事圣经查阅"
    description: str = (
        "查阅故事圣经中的设定资料，包括人物卡片、世界观、力量体系、文风指南等。"
        "输入要查阅的类别：characters（人物）、worldview（世界观）、"
        "power_system（力量体系）、style_guide（文风指南）、all（全部）。"
    )

    def _run(self, category: str = "all") -> str:
        category = category.strip().lower()
        output_parts = []
        current_bible = bible_dir()

        if category in ("all", "characters", "人物"):
            chars_dir = current_bible / "characters"
            if chars_dir.exists():
                for f in sorted(chars_dir.glob("*.md")):
                    output_parts.append(f"## 人物：{f.stem}\n{f.read_text(encoding='utf-8')}")

        if category in ("all", "worldview", "世界观"):
            wv_dir = current_bible / "worldview"
            if wv_dir.exists():
                for f in sorted(wv_dir.glob("*.md")):
                    output_parts.append(f"## 世界观：{f.stem}\n{f.read_text(encoding='utf-8')}")

        if category in ("all", "power_system", "力量体系"):
            ps_file = current_bible / "power_system.md"
            if ps_file.exists():
                output_parts.append(f"## 力量体系\n{ps_file.read_text(encoding='utf-8')}")

        if category in ("all", "style_guide", "文风指南"):
            sg_file = current_bible / "style_guide.md"
            if sg_file.exists():
                output_parts.append(f"## 文风指南\n{sg_file.read_text(encoding='utf-8')}")

        if not output_parts:
            return (
                f"未找到类别 '{category}' 的设定资料。"
                "可用类别：characters, worldview, power_system, style_guide, all"
            )
        return "\n\n---\n\n".join(output_parts)
