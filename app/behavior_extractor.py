"""
行为标签提取引擎
将康复师的随手文字记录映射为结构化行为标签(taxonomy驱动)

核心逻辑:
1. 加载taxonomy, 为每个行为构建关键词索引
2. 对输入文本分句, 在每个句子中匹配行为关键词
3. 在匹配句子的上下文中检测方向词(进步/退步/稳定)
4. 数量方向词(增加/减少)按行为类型解释极性:
   目标行为: 增加→+1, 减少→-1
   问题行为: 减少→+1(问题减轻=好事), 增加→-1(问题加重=坏事)
   质量方向词(进步/退步/恶化等)对所有行为统一: 好消息→+1, 坏消息→-1
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


def _find_direction(sentence: str, direction_words: dict, is_target: bool) -> Direction:
    """在句子中检测方向词

    语义统一为"对干预目标的好坏":
    - positive = 好消息(目标行为进步 / 问题行为减轻)
    - negative = 坏消息(目标行为退步 / 问题行为加重)

    数量方向词(increase/decrease)需结合 is_target 解释:
    - 目标行为(希望提升): 增加=好, 减少=坏
    - 问题行为(希望减少): 减少=好, 增加=坏

    匹配采用长词优先+区间占用, 避免"不能"包含"能"、
    "稳定不变"包含"稳定"等子串冲突导致的误判。
    """
    polarity_map = [
        ("positive", "pos"),
        ("negative", "neg"),
        ("neutral", "neu"),
        ("increase", "inc"),
        ("decrease", "dec"),
    ]
    # 构建 (词, 极性) 列表, 按词长降序, 长词优先匹配
    word_polarity = []
    for list_key, pol in polarity_map:
        for w in direction_words.get(list_key, []):
            word_polarity.append((w, pol))
    word_polarity.sort(key=lambda x: -len(x[0]))

    consumed = [False] * len(sentence)
    counts = {"pos": 0, "neg": 0, "neu": 0, "inc": 0, "dec": 0}
    for word, pol in word_polarity:
        start = 0
        while True:
            idx = sentence.find(word, start)
            if idx == -1:
                break
            if not any(consumed[idx:idx + len(word)]):
                counts[pol] += 1
                for i in range(idx, idx + len(word)):
                    consumed[i] = True
            start = idx + len(word)

    # 数量词按 is_target 归并到 pos/neg
    if is_target:
        counts["pos"] += counts["inc"]  # 目标行为增加 = 好
        counts["neg"] += counts["dec"]  # 目标行为减少 = 坏
    else:
        counts["pos"] += counts["dec"]  # 问题行为减少 = 好
        counts["neg"] += counts["inc"]  # 问题行为增加 = 坏

    pos, neg, neu = counts["pos"], counts["neg"], counts["neu"]
    if pos > neg and pos > 0:
        return Direction.POSITIVE
    elif neg > pos and neg > 0:
        return Direction.NEGATIVE
    elif neu > 0:
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


def _compute_score(direction: Direction) -> float:
    """计算得分

    direction 已统一编码"对干预目标的好坏":
    positive=+1(目标进步/问题减轻), negative=-1(目标退步/问题加重), neutral=0
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

                direction = _find_direction(sentence, direction_words, is_target)
                score = _compute_score(direction)
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