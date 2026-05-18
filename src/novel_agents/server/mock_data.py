"""Mock 模式下的逐 Agent 输出与本章生成的"账本数据"

Mock 模式不仅要演示 6→9 Agent 的流水线，
还要生成一份完整的「章节副产物包」：
- KPI JSON
- 标题候选 5 个
- 章节摘要 200 字
- 金句 2-3 句
- 伏笔变动（新埋 1-2 个、可能回收 1 个）
- 角色 runtime 更新
- AI 味硬检测报告
- 简介迭代候选 3 个
- 成本估算（基于真实 token 模拟）

这样无 API Key 用户也能完整体验整个"爆款工业流水线"。
"""

from __future__ import annotations

import random
from typing import Any

# 各 Agent 在 mock 模式下的逐步骤输出文本（含 9 个 Agent）
MOCK_OUTPUTS: dict[str, list[str]] = {
    "arc_architect": [
        "📐 本卷《蛰伏》卷纲 — 章 1-15：",
        "节点 1（章 1-3）：开局抓人 / 重生觉醒 / 装弱反差。",
        "节点 2（章 4-7）：内门大比报名 / 暗修混沌吞天诀 / 首次小爽点（碾压同阶）。",
        "节点 3（章 8-11）：危机骤起 / 赵天铭暴露野心 / 主角隐忍布局。",
        "节点 4（章 12-14）：转折反杀 / 借机缘提升 / 中爽点。",
        "节点 5（章 15）：卷末炸点 / 击败筑基对手 / 钩子衔接第二卷。",
        (
            "本卷伏笔池：F001 血衣楼内奸（深度 30 章）/ "
            "F002 师妹身世（深度 5 章）/ F003 玉简来历（深度 12 章）。"
        ),
    ],
    "planner": [
        "本章核心事件：少年陈尘在乱葬岗目睹师兄陨落，意外得到一枚残破玉简。",
        "情绪曲线设计：压抑（蹲守）→ 紧张（追杀）→ 暴怒（师兄陨落）→ 破釜沉舟。",
        (
            "Beats: 1) 黄昏乱葬岗蹲守; 2) 师兄重伤逃来; 3) 黑袍人追至; "
            "4) 师兄交付玉简; 5) 少年怒夺玉简; 6) 玉简共鸣识主。"
        ),
        "钩子：玉简中传来一道沙哑笑声——'小子，可愿拜我为师？'",
    ],
    "pacing_doctor": [
        "🎚 节奏处方 — 本章定级：『大爽 + 钩子双拼』",
        "爽点目标 8.0/10（首次老怪物认主，强力反差）。",
        "金手指强度：等级 3/10（仅识主，未灌输神通，保后期空间）。",
        "金句目标：≥ 2 句；章末钩子：S 级。",
        "前 3 章爽点强度建议：5→6→8（指数微爬升）。",
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
        "📊 网文 KPI 评估：追订率 0.78 / 钩子强度 0.85 / 节奏 0.80 / 沉浸 0.82 / AI 味 0.22",
        "评分：43/50 - 各维度均衡，钩子 S 级。",
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
    "marketing_specialist": [
        "🎯 5 个候选章节标题已生成（含点击钩子）",
        "1) 我，杂役弟子，被老怪物盯上了",
        "2) 师兄死前塞给我一枚玉简，玉简里有人在笑",
        "3) 黑袍人三丈外停下，他说留我全尸",
        "4) 重生第七日，我等到了那枚玉简",
        "5) 比泪更烫的，是我十六岁那年的恨",
        "📣 章末追读语：『老怪物到底是谁？为什么偏偏认他为主？下章揭晓。』",
        "📖 简介迭代候选 3 个已写入 bible/marketing_synopsis.md",
    ],
}

# 章节副产物模拟数据（KPI / 标题 / 金句 / 伏笔变动 / 角色更新）
MOCK_HIGHLIGHTS: list[str] = [
    "比泪更烫的东西",
    "笑里有泪，也有别的什么",
]

MOCK_TITLE_CANDIDATES: list[dict[str, Any]] = [
    {"title": "我，杂役弟子，被老怪物盯上了", "angle": "身份反差+悬念", "score": 8.6},
    {"title": "师兄死前塞给我一枚玉简，玉简里有人在笑", "angle": "冲突+诡异", "score": 8.9},
    {"title": "黑袍人三丈外停下，他说留我全尸", "angle": "极端冲突+悬念", "score": 8.4},
    {"title": "重生第七日，我等到了那枚玉简", "angle": "重生+期待", "score": 7.9},
    {"title": "比泪更烫的，是我十六岁那年的恨", "angle": "情感+复仇", "score": 8.2},
]

MOCK_FORESHADOWING_PLANTS: list[dict[str, Any]] = [
    {
        "title": "玉简中的沙哑笑声",
        "planted_chapter": 1,
        "planned_payoff_chapter": 12,
        "importance": "high",
        "status": "planted",
        "description": "玉简识主时浮出沙哑笑声，暗示老怪物身份（实为前世仇敌之师）",
        "related_characters": ["陈尘", "玉简老怪物"],
    },
    {
        "title": "黑袍人腰间噬魂幡纹路",
        "planted_chapter": 1,
        "planned_payoff_chapter": 6,
        "importance": "medium",
        "status": "planted",
        "description": "黑袍人法器纹路与赵家家徽吻合，暗示血衣楼与外门叛徒关联",
        "related_characters": ["黑袍人", "赵天铭"],
    },
]

MOCK_CHARACTER_UPDATES: list[dict[str, Any]] = [
    {
        "name": "陈尘",
        "snapshot": {
            "realm": "练气七层",
            "mood": "暗藏杀机的隐忍",
            "knot": "师兄陨落 + 血衣楼仇恨累积",
            "key_relations": ["与师兄：陨落于本章", "与玉简老怪物：师徒契约成立"],
            "status": "获得玉简，未暴露重生身份",
            "notes": "情绪从压抑转向破釜沉舟，开始进入主动布局阶段",
        },
    },
]

MOCK_KPI: dict[str, Any] = {
    "retention_score": 0.78,
    "hook_strength": 0.85,
    "immersion_score": 0.82,
    "character_voice_score": 0.74,
    "pace_score": 0.80,
    "overall_score": 0.79,
    "excitement_peaks": 3,
    "slap_face_count": 0,
    "cliffhanger_count": 2,
    "golden_lines": 2,
    "ai_taste_score": 0.22,
    "notes": "钩子 S 级；情绪铺垫到位；建议章首压缩。",
}

MOCK_SUMMARY: str = (
    "陈尘黄昏潜伏乱葬岗，目睹被血衣楼追杀的师兄重伤逃来。"
    "他咬牙忍下情绪，从濒死师兄手中接过玄阴玉简后，"
    "黑袍杀手追至，三丈外冷声索物。陈尘忽然笑了，笑里有别于泪的烫意，"
    "他摸出玉简，玉简上浮现一行沙哑文字——『小子，可愿拜我为师？』。"
    "本章奠定主角隐忍 + 复仇基调，玉简认主成立第一根金手指线。"
)

MOCK_AI_LINT_SAMPLE: dict[str, Any] = {
    "score": 0.18,
    "level": "良好",
    "metrics": {
        "blacklist_per_kchar": 0.4,
        "transition_per_kchar": 3.2,
        "sentence_cv": 0.61,
        "max_head_repeat_streak": 2,
    },
    "issues": [],
    "suggestions": [
        "章首『暮色铺陈』可再短一拍，符合开篇 3 章节奏要求。",
    ],
}

MOCK_SYNOPSIS_CANDIDATES: list[str] = [
    (
        "前世他是合体期剑帝，被血衣楼算计陨落。重生回到十六岁，"
        "他是天玄宗最不起眼的杂役弟子，却握着千年记忆与元婴神识。"
        "这一世，他要杀回血衣楼。"
    ),
    (
        "我叫陈尘，十六岁，练气三层。"
        "但你不知道——我有一千年的修炼记忆，和一道能看穿一切的神识。"
        "这一世，从被你们瞧不起开始。"
    ),
    (
        "重生第七日，老怪物认我为徒。"
        "我等了一千年，等的就是这一刻。"
        "血衣楼？三年后我亲自上门拜访。"
    ),
]


# 每个 Agent 在 mock 模式下的执行步长
MOCK_STEPS: dict[str, tuple[int, tuple[float, float]]] = {
    "arc_architect": (4, (0.4, 0.7)),
    "planner": (5, (0.35, 0.7)),
    "pacing_doctor": (3, (0.3, 0.55)),
    "world_builder": (4, (0.3, 0.6)),
    "writer": (8, (0.5, 1.1)),
    "reviewer": (5, (0.35, 0.7)),
    "polisher": (7, (0.4, 0.9)),
    "reader_sim": (4, (0.3, 0.55)),
    "marketing_specialist": (4, (0.3, 0.55)),
}


def randomize_kpi(seed_chapter: int) -> dict[str, Any]:
    """每章生成略有差异的 KPI 数据，模拟自然波动"""
    rng = random.Random(seed_chapter * 991 + 17)
    base = dict(MOCK_KPI)
    for k in (
        "retention_score",
        "hook_strength",
        "immersion_score",
        "character_voice_score",
        "pace_score",
        "overall_score",
    ):
        base[k] = round(min(1.0, max(0.4, base[k] + rng.uniform(-0.1, 0.08))), 3)
    base["excitement_peaks"] = max(1, MOCK_KPI["excitement_peaks"] + rng.randint(-1, 2))
    base["golden_lines"] = max(0, MOCK_KPI["golden_lines"] + rng.randint(-1, 2))
    base["ai_taste_score"] = round(
        min(0.7, max(0.05, MOCK_KPI["ai_taste_score"] + rng.uniform(-0.08, 0.12))), 3
    )
    return base
