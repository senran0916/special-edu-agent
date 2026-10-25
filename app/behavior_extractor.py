"""
行为标签提取引擎
将康复师的随手文字记录映射为结构化行为标签(taxonomy驱动)

核心逻辑:
1. 加载taxonomy, 为每个行为构建关键词索引
2. 对输入文本分句, 在每个句子中匹配行为关键词
3. 在匹配句子的上下文中检测方向词(进步/退步/稳定)
4. 对目标行为: 正向词→+1, 负向词→-1
   对问题行为: 正向词(如"减少")→+1(问题减轻=好事), 负向词(如"频繁")→-1
5. 尝试推断能力等级(level_hint)
"""
import json
import os
import re
from typing import List, Optional

from app.models import BehaviorTag, Direction

TAXONOMY_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "taxonomy.json")

# 全局缓存taxonomy
_taxonomy_cache = None


def load_taxonomy() -> dict:
    """加载并缓存taxonomy"""
    global _taxonomy_cache
    if _taxonomy_cache is None:
        with open(TAXONOMY_PATH, "r", encoding="utf-8") as f:
            _taxonomy_cache = json.load(f)
    return _taxonomy_cache


def _split_sentences(text: str) -> List[str]:
    """简单中文分句"""
    # 按标点切分, 保留完整句子
    sentences = re.split(r"[。！？；\n]+", text)
    return [s.strip() for s in sentences if s.strip() and len(s.strip()) >= 2]


def _find_direction(sentence: str, direction_words: dict) -> Direction:
    """在句子中检测方向词"""
    pos_hits = sum(1 for w in direction_words["positive"] if w in sentence)
    neg_hits = sum(1 for w in direction_words["negative"] if w in sentence)
    neu_hits = sum(1 for w in direction_words["neutral"] if w in sentence)

    if pos_hits > neg_hits and pos_hits > 0:
        return Direction.POSITIVE
    elif neg_hits > pos_hits and neg_hits > 0:
        return Direction.NEGATIVE
    elif neu_hits > 0:
        return Direction.NEUTRAL
    # 默认: 提到了但无方向词, 视为中性观察
    return Direction.NEUTRAL


def _infer_level(sentence: str, levels: List[str]) -> Optional[str]:
    """尝试从句子推断能力等级

    策略: 等级列表通常从低到高排列(从差到好)
    - 如果句子有强正向词(学会/独立/第一次) → 最高等级
    - 如果句子有负向词(不能/无法) → 最低等级
    - 否则 → 中间等级
    """
    if not levels:
        return None
    strong_positive = ["学会", "独立", "第一次", "自发", "主动", "成功", "做到了"]
    strong_negative = ["不能", "无法", "完全", "从不", "没有"]

    if any(w in sentence for w in strong_positive):
        return levels[-1]
    if any(w in sentence for w in strong_negative):
        return levels[0]
    return None  # 无法确定时不猜


def _compute_score(direction: Direction, is_target: bool) -> float:
    """计算得分

    目标行为(希望提升): positive=+1, negative=-1
    问题行为(希望减少): positive=+1(问题减轻), negative=-1(问题加重)
    统一逻辑: positive永远=+1, negative永远=-1, 因为方向词已经
    在语义上反映了"变好"还是"变差"
    """
    if direction == Direction.POSITIVE:
        return 1.0
    elif direction == Direction.NEGATIVE:
        return -1.0
    return 0.0


def extract_behaviors(content: str) -> List[BehaviorTag]:
    """从一段康复记录文字中提取结构化行为标签

    Args:
        content: 康复师的随手记录原文

    Returns:
        提取出的行为标签列表(去重合并同一行为)
    """
    taxonomy = load_taxonomy()
    direction_words = taxonomy["direction_words"]
    sentences = _split_sentences(content)

    # 用字典聚合: key = behavior_id, 避免同一行为多次匹配产生重复
    tag_map = {}

    for sentence in sentences:
        for domain in taxonomy["domains"]:
            is_target = domain["is_target"]
            for behavior in domain["behaviors"]:
                matched = [kw for kw in behavior["keywords"] if kw in sentence]
                if not matched:
                    continue

                direction = _find_direction(sentence, direction_words)
                score = _compute_score(direction, is_target)
                level_hint = _infer_level(sentence, behavior.get("levels", []))

                key = behavior["id"]
                if key in tag_map:
                    # 同一行为多次出现: 累计得分, 合并关键词
                    existing = tag_map[key]
                    existing.score += score
                    existing.matched_keywords = list(
                        set(existing.matched_keywords + matched)
                    )
                    if direction == Direction.POSITIVE:
                        existing.direction = Direction.POSITIVE
                    elif (
                        direction == Direction.NEGATIVE
                        and existing.direction != Direction.POSITIVE
                    ):
                        existing.direction = Direction.NEGATIVE
                    if level_hint and not existing.level_hint:
                        existing.level_hint = level_hint
                    # 补充证据
                    if sentence not in existing.evidence:
                        existing.evidence = existing.evidence + " | " + sentence
                else:
                    tag_map[key] = BehaviorTag(
                        behavior_id=behavior["id"],
                        behavior_name=behavior["name"],
                        domain_id=domain["id"],
                        domain_name=domain["name"],
                        direction=direction,
                        score=score,
                        matched_keywords=matched,
                        evidence=sentence,
                        level_hint=level_hint,
                    )

    return list(tag_map.values())


def extract_and_summarize(content: str) -> dict:
    """提取行为标签并返回可读摘要(用于Coze快速展示)"""
    tags = extract_behaviors(content)
    if not tags:
        return {
            "tags": [],
            "tag_count": 0,
            "domains_covered": [],
            "quick_summary": "未识别到明确的行为标签, 建议补充更具体的观察描述。",
        }

    domains = list(set(t.domain_name for t in tags))
    positive_tags = [t for t in tags if t.direction == Direction.POSITIVE]
    negative_tags = [t for t in tags if t.direction == Direction.NEGATIVE]

    parts = []
    if positive_tags:
        names = "、".join(t.behavior_name for t in positive_tags)
        parts.append(f"进步方面: {names}")
    if negative_tags:
        names = "、".join(t.behavior_name for t in negative_tags)
        parts.append(f"需关注: {names}")

    return {
        "tags": [t.model_dump(mode="json") for t in tags],
        "tag_count": len(tags),
        "domains_covered": domains,
        "quick_summary": "; ".join(parts) if parts else "本次记录以中性观察为主。",
    }