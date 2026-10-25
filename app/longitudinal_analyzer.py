"""
纵向时序分析模块
对儿童的历史康复记录进行时间序列分析:
- 按周聚合行为得分
- 计算线性趋势斜率
- 对比近期与前期变化
- 输出每个行为的趋势标签
"""
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from collections import defaultdict

from app.models import StoredRecord, DomainTrend, Direction
from app.behavior_extractor import load_taxonomy


def _parse_date(date_str: str) -> datetime:
    """解析日期字符串"""
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(date_str[:19], fmt)
        except ValueError:
            continue
    return datetime.now()


def _week_key(dt: datetime) -> str:
    """生成周标识 (ISO年份-周数)"""
    iso = dt.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _linear_slope(values: List[float]) -> float:
    """简单线性回归斜率(最小二乘法)
    返回每步的变化率, 正=上升, 负=下降
    """
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n
    numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _label_trend(slope: float, is_target: bool, total_mentions: int) -> str:
    """根据斜率生成趋势标签

    目标行为: 斜率>0 = improving, <0 = declining
    问题行为: 斜率>0 = improving(问题减轻), <0 = declining(问题加重)
    (因为score已经统一为: 正=好, 负=差)
    """
    if total_mentions < 2:
        return "insufficient_data"

    # 斜率阈值: 每周变化超过0.15视为明显趋势
    if slope > 0.15:
        return "improving"
    elif slope < -0.15:
        return "declining"
    else:
        return "stable"


def analyze_longitudinal(
    records: List[StoredRecord],
    period_days: int = 90,
) -> List[DomainTrend]:
    """对历史记录做纵向趋势分析

    Args:
        records: 按日期升序排列的记录列表
        period_days: 分析窗口

    Returns:
        每个被提及过的行为的趋势列表
    """
    taxonomy = load_taxonomy()
    # 构建行为→领域映射和is_target映射
    behavior_meta = {}
    for domain in taxonomy["domains"]:
        for behavior in domain["behaviors"]:
            behavior_meta[behavior["id"]] = {
                "behavior_name": behavior["name"],
                "domain_id": domain["id"],
                "domain_name": domain["name"],
                "is_target": domain["is_target"],
            }

    now = datetime.now()
    cutoff = now - timedelta(days=period_days)
    recent_cutoff = now - timedelta(days=14)  # 近2周
    previous_cutoff = now - timedelta(days=28)  # 前2周

    # 按行为聚合: 周得分序列
    weekly_scores = defaultdict(lambda: defaultdict(float))  # bid -> week_key -> score
    behavior_mentions = defaultdict(int)
    behavior_pos = defaultdict(int)
    behavior_neg = defaultdict(int)
    recent_scores = defaultdict(float)
    previous_scores = defaultdict(float)

    for record in records:
        dt = _parse_date(record.session_date)
        if dt < cutoff:
            continue

        wk = _week_key(dt)
        for tag in record.behavior_tags:
            bid = tag.behavior_id
            behavior_mentions[bid] += 1
            if tag.direction == Direction.POSITIVE:
                behavior_pos[bid] += 1
            elif tag.direction == Direction.NEGATIVE:
                behavior_neg[bid] += 1

            weekly_scores[bid][wk] += tag.score

            if dt >= recent_cutoff:
                recent_scores[bid] += tag.score
            elif dt >= previous_cutoff:
                previous_scores[bid] += tag.score

    # 构建趋势结果
    trends = []
    for bid, meta in behavior_meta.items():
        mentions = behavior_mentions.get(bid, 0)
        if mentions == 0:
            continue  # 该行为从未被提及, 不输出

        # 按周排序得分序列
        week_data = weekly_scores.get(bid, {})
        sorted_weeks = sorted(week_data.keys())
        score_series = [week_data[w] for w in sorted_weeks]

        slope = _linear_slope(score_series)
        is_target = meta["is_target"]
        label = _label_trend(slope, is_target, mentions)

        recent = recent_scores.get(bid, 0.0)
        previous = previous_scores.get(bid, 0.0)

        trends.append(DomainTrend(
            domain_id=meta["domain_id"],
            domain_name=meta["domain_name"],
            behavior_id=bid,
            behavior_name=meta["behavior_name"],
            is_target=is_target,
            total_mentions=mentions,
            positive_count=behavior_pos.get(bid, 0),
            negative_count=behavior_neg.get(bid, 0),
            net_score=sum(score_series),
            trend_slope=round(slope, 3),
            trend_label=label,
            recent_score=recent,
            previous_score=previous,
            period_change=round(recent - previous, 3),
        ))

    # 按领域分组排序, 同领域内按提及次数降序
    trends.sort(key=lambda t: (t.domain_id, -t.total_mentions))
    return trends


def build_summary(trends: List[DomainTrend]) -> Dict:
    """基于趋势数据构建整体摘要"""
    if not trends:
        return {
            "highlights": [],
            "concerns": [],
            "overall": "数据不足, 暂无法生成纵向分析摘要。",
        }

    highlights = [
        f"{t.behavior_name}呈上升趋势(近2周得分{t.recent_score:+.1f})"
        for t in trends
        if t.trend_label == "improving"
    ]
    concerns = [
        f"{t.behavior_name}呈下降趋势(近2周得分{t.recent_score:+.1f})"
        for t in trends
        if t.trend_label == "declining"
    ]
    stagnations = [
        f"{t.behavior_name}长期停滞(提及{t.total_mentions}次, 无明显变化)"
        for t in trends
        if t.trend_label == "stable" and t.total_mentions >= 4 and t.is_target
    ]

    total_target = sum(1 for t in trends if t.is_target)
    improving_target = sum(1 for t in trends if t.is_target and t.trend_label == "improving")

    if total_target > 0:
        pct = round(improving_target / total_target * 100)
        overall = f"在{total_target}项目标行为中, {improving_target}项呈上升趋势({pct}%)。"
        if concerns:
            overall += f" 需重点关注{len(concerns)}项下降趋势。"
        if stagnations:
            overall += f" {len(stagnations)}项目标行为停滞, 建议调整干预策略。"
    else:
        overall = "记录中目标行为数据较少, 建议增加观察频次。"

    return {
        "highlights": highlights[:5],
        "concerns": concerns[:5],
        "stagnations": stagnations[:5],
        "overall": overall,
    }