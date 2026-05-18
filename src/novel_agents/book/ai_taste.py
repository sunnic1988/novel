"""AI 味硬检测器 — 不依赖 LLM 的规则算法

输出 0~1 的 AI 味分数（越高越像 AI），并给出可执行的修改建议。

检测维度：
1. 黑名单词频（"然而"/"不过"/"与此同时" 等典型 AI 转折词）
2. 句首词重复（连续多句以"他/她/这"开头）
3. 句长方差（AI 倾向均长 28-32 字，方差小）
4. 排比密度（连续 3 段以上结构相同）
5. 章末总结句（"本章/这一章" 等）
6. 抽象名词密度（"意识/某种/某种程度" 等）
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from typing import Any

# 来自 bible/style_guide.md "绝对禁止的AI八股词" + 实战补充
BLACKLIST_WORDS: list[str] = [
    "总之", "综上所述", "总而言之",
    "值得一提的是", "不可否认",
    "某种程度上", "从某种意义上说", "在某种意义上",
    "毋庸置疑", "显而易见",
    "与此同时",
    "事实上", "实际上",
    "不禁",
    "本章", "这一章",
    "首先", "其次", "再次", "最后",
    "由此可见", "由此", "由此可知",
    "可以说", "不得不说", "不得不",
    "意识到", "他意识到", "她意识到",
    "正如", "正如所言", "诚如",
]

# AI 偏爱的转折/连接词（密度过高就是 AI 味）
TRANSITION_WORDS: list[str] = [
    "然而", "不过", "但是", "可是", "却",
    "于是", "因此", "所以", "因而", "故此",
]


@dataclass
class AITasteReport:
    score: float  # 0 ~ 1
    chinese_chars: int
    sentence_count: int
    issues: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 4),
            "level": (
                "极高" if self.score >= 0.7
                else "偏高" if self.score >= 0.45
                else "中等" if self.score >= 0.25
                else "良好"
            ),
            "chinese_chars": self.chinese_chars,
            "sentence_count": self.sentence_count,
            "issues": self.issues,
            "metrics": self.metrics,
            "suggestions": self.suggestions,
        }


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？!?\n])\s*", text)
    return [s.strip() for s in parts if s.strip()]


def _count_chinese(text: str) -> int:
    return sum(1 for c in text if "\u4e00" <= c <= "\u9fff")


def analyze(text: str) -> AITasteReport:
    """对一段正文做 AI 味硬检测，返回结构化报告。"""
    text = text or ""
    sentences = _split_sentences(text)
    ch_count = _count_chinese(text)
    sent_count = len(sentences)
    issues: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {}
    suggestions: list[str] = []

    if ch_count < 50:
        # 文本太短，无法可靠评估
        return AITasteReport(
            score=0.0,
            chinese_chars=ch_count,
            sentence_count=sent_count,
            metrics={"too_short": True},
        )

    score = 0.0

    # 1. 黑名单词频
    blacklist_hits: dict[str, int] = {}
    for w in BLACKLIST_WORDS:
        cnt = text.count(w)
        if cnt > 0:
            blacklist_hits[w] = cnt
    bl_total = sum(blacklist_hits.values())
    # 每 1000 字超过 2 次就开始扣分
    bl_per_kch = bl_total / max(ch_count / 1000.0, 1.0)
    bl_score = min(bl_per_kch / 6.0, 1.0)
    score += bl_score * 0.35
    metrics["blacklist_hits"] = blacklist_hits
    metrics["blacklist_per_kchar"] = round(bl_per_kch, 3)
    if blacklist_hits:
        issues.append({
            "kind": "blacklist",
            "count": bl_total,
            "samples": list(blacklist_hits.items())[:8],
        })
        suggestions.append(
            f"出现 {bl_total} 次 AI 八股词（{', '.join(list(blacklist_hits.keys())[:5])}…）"
            "，请逐一改写为具体动作/对话/场景。"
        )

    # 2. 转折词密度
    trans_total = sum(text.count(w) for w in TRANSITION_WORDS)
    trans_per_kch = trans_total / max(ch_count / 1000.0, 1.0)
    # 每千字 >= 6 次开始扣
    trans_score = min(max(trans_per_kch - 5, 0) / 8.0, 1.0)
    score += trans_score * 0.10
    metrics["transition_per_kchar"] = round(trans_per_kch, 3)
    if trans_per_kch >= 6:
        issues.append({"kind": "transitions", "per_kchar": trans_per_kch})
        suggestions.append(
            "转折/连接词密度偏高，多用动作/场景切换替代"
            "「然而/于是/不过」。"
        )

    # 3. 句长方差
    sent_lens = [len(s) for s in sentences if len(s) >= 4]
    if len(sent_lens) >= 8:
        mean = statistics.mean(sent_lens)
        stdev = statistics.pstdev(sent_lens)
        cv = stdev / mean if mean else 0
        metrics["sentence_mean_len"] = round(mean, 1)
        metrics["sentence_stdev"] = round(stdev, 1)
        metrics["sentence_cv"] = round(cv, 3)
        # 网文标准 CV 应 >= 0.55，AI 文本常 < 0.4
        if cv < 0.4:
            penalty = (0.4 - cv) / 0.4
            score += penalty * 0.18
            issues.append({"kind": "uniform_sentence_length", "cv": cv})
            suggestions.append(
                f"句长过于均匀（变异系数 {cv:.2f}）— 加入更多短句"
                "/单字成段制造节奏。"
            )

    # 4. 句首词重复
    head_words: list[str] = []
    for s in sentences:
        head = s[:2] if len(s) >= 2 else s
        head_words.append(head)
    head_repeat_streaks: list[tuple[str, int]] = []
    if head_words:
        cur_word = head_words[0]
        cur_streak = 1
        max_streak = 1
        worst_head = cur_word
        for h in head_words[1:]:
            if h == cur_word:
                cur_streak += 1
                if cur_streak > max_streak:
                    max_streak = cur_streak
                    worst_head = h
            else:
                cur_word = h
                cur_streak = 1
        if max_streak >= 3:
            head_repeat_streaks.append((worst_head, max_streak))
            penalty = min((max_streak - 2) * 0.08, 0.15)
            score += penalty
            issues.append(
                {"kind": "repeated_sentence_head", "head": worst_head, "streak": max_streak}
            )
            suggestions.append(
                f"连续 {max_streak} 句以「{worst_head}」开头，"
                "变换句首（动作/对话/环境切入）。"
            )
    metrics["max_head_repeat_streak"] = (
        head_repeat_streaks[0][1] if head_repeat_streaks else 1
    )

    # 5. 排比 / 三段式
    triplets = re.findall(
        r"([^\n。！？]{4,30}[。！？])\s*([^\n。！？]{4,30}[。！？])\s*([^\n。！？]{4,30}[。！？])",
        text,
    )
    # 简单近似：检测以同样字开头的三句相邻
    parallel_count = 0
    for s1, s2, s3 in triplets:
        if s1[:1] == s2[:1] == s3[:1]:
            parallel_count += 1
    metrics["parallel_triplet_count"] = parallel_count
    if parallel_count >= 2:
        score += min(parallel_count * 0.05, 0.12)
        issues.append({"kind": "parallel_triplets", "count": parallel_count})
        suggestions.append(
            f"检测到 {parallel_count} 处三段式排比，打散为不同句式。"
        )

    # 6. 章末总结
    tail = text[-200:]
    summary_hits = sum(tail.count(w) for w in ["本章", "这一章", "总而言之", "综上"])
    if summary_hits >= 1:
        score += 0.08
        issues.append({"kind": "ending_summary", "hits": summary_hits})
        suggestions.append("章末出现总结性语言，改用具体动作或对话收尾。")

    score = max(0.0, min(score, 1.0))

    return AITasteReport(
        score=score,
        chinese_chars=ch_count,
        sentence_count=sent_count,
        issues=issues,
        metrics=metrics,
        suggestions=suggestions,
    )
