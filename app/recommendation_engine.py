"""
训练方案推荐引擎
基于纵向趋势和异常预警, 生成训练方案调整建议

推荐策略:
- 强改善 → 维持并进阶
- 停滞 → 变换策略(材料/步骤拆解/场景泛化)
- 退化 → 回退难度+排查环境
- 问题行为加重 → FBA+前事策略
- 资源分配: 优先处理high严重度异常, 再处理停滞领域
"""
from typing import List
from app.models import DomainTrend, AnomalyAlert, Recommendation


def generate_recommendations(
    trends: List[DomainTrend],
    alerts: List[AnomalyAlert],
) -> List[Recommendation]:
    """生成训练方案调整建议

    Args:
        trends: 纵向趋势列表
        alerts: 异常预警列表

    Returns:
        按优先级排序的建议列表
    """
    recs = []

    # ===== 第一优先级: 处理high严重度异常 =====
    for alert in alerts:
        if alert.severity != "high":
            continue
        priority = "high"
        if alert.alert_type == "regression":
            recs.append(Recommendation(
                priority=priority,
                domain_id=alert.domain_id,
                domain_name=alert.domain_name,
                current_state=f"{alert.behavior_name}出现退化迹象",
                action=(
                    f"立即降低{alert.behavior_name}相关任务的难度, "
                    "回到孩子上次成功完成的水平, 用2-3次成功体验重建信心后, "
                    "再以更小的梯度提升要求。同时与家长沟通, 排查家庭环境、"
                    "作息、人员是否有近期变动。"
                ),
                rationale=alert.description,
                target_behaviors=[alert.behavior_name],
            ))
        elif alert.alert_type == "spike":
            recs.append(Recommendation(
                priority=priority,
                domain_id=alert.domain_id,
                domain_name=alert.domain_name,
                current_state=f"问题行为「{alert.behavior_name}」激增",
                action=(
                    f"本周优先安排{alert.behavior_name}的功能行为评估(FBA), "
                    "连续记录3-5次该行为发生的前因(A)-行为(B)-后果(C), "
                    "确定其功能后, 教授功能等价的替代行为, "
                    "并调整前事策略(如调整任务时长、提供选择权、预告转换)。"
                ),
                rationale=alert.description,
                target_behaviors=[alert.behavior_name],
            ))

    # ===== 第二优先级: 停滞领域策略调整 =====
    for t in trends:
        if not t.is_target:
            continue
        if t.trend_label == "stable" and t.total_mentions >= 3 and t.net_score <= 1:
            # 检查是否已有high异常覆盖该行为
            covered = any(
                a.behavior_id == t.behavior_id and a.severity == "high"
                for a in alerts
            )
            if covered:
                continue
            recs.append(Recommendation(
                priority="medium",
                domain_id=t.domain_id,
                domain_name=t.domain_name,
                current_state=(
                    f"{t.behavior_name}进展缓慢(净得分{t.net_score:+.1f}, "
                    f"斜率{t.trend_slope:+.2f})"
                ),
                action=(
                    f"针对{t.behavior_name}尝试以下调整之一: "
                    "1)更换教学材料或强化物以提升动机; "
                    "2)将目标技能拆解为更小的步骤, 确保每步成功率>80%; "
                    "3)在不同场景(个训室/教室/家庭)中泛化该技能; "
                    "4)若持续2周仍无进展, 考虑暂时降低该目标优先级, "
                    "将资源转向进展更好的领域以建立成功感。"
                ),
                rationale=(
                    f"该行为在{t.total_mentions}次记录中未呈现明显改善趋势, "
                    "提示当前干预可能遇到了动机或难度匹配问题。"
                ),
                target_behaviors=[t.behavior_name],
            ))

        elif t.trend_label == "declining" and t.is_target:
            covered = any(
                a.behavior_id == t.behavior_id and a.severity == "high"
                for a in alerts
            )
            if covered:
                continue
            recs.append(Recommendation(
                priority="medium",
                domain_id=t.domain_id,
                domain_name=t.domain_name,
                current_state=f"{t.behavior_name}呈下降趋势",
                action=(
                    f"关注{t.behavior_name}的下降趋势。检查近期训练是否"
                    "难度提升过快或强化 schedule 是否改变。建议本周增加"
                    "该技能的维持训练(已掌握项目的复习), 减少新技能引入。"
                ),
                rationale=(
                    f"斜率{t.trend_slope:+.2f}, 近2周变化{t.period_change:+.1f}。"
                ),
                target_behaviors=[t.behavior_name],
            ))

    # ===== 第三优先级: 优势领域进阶 =====
    improving_targets = [
        t for t in trends
        if t.is_target and t.trend_label == "improving" and t.total_mentions >= 3
    ]
    # 挑选改善最明显的1-2个领域给出进阶建议
    improving_targets.sort(key=lambda t: -t.trend_slope)
    for t in improving_targets[:2]:
        recs.append(Recommendation(
            priority="low",
            domain_id=t.domain_id,
            domain_name=t.domain_name,
            current_state=f"{t.behavior_name}进展良好(斜率{t.trend_slope:+.2f})",
            action=(
                f"{t.behavior_name}当前干预策略有效, 建议维持。"
                "可考虑: 1)逐步提高任务复杂度或延长要求持续时间; "
                "2)将训练从结构化场景向自然情境过渡; "
                "3)开始引导同伴互动中的泛化应用。"
            ),
            rationale="利用上升势头加速技能泛化和进阶, 巩固干预成果。",
            target_behaviors=[t.behavior_name],
        ))

    # ===== 排序: high > medium > low =====
    priority_order = {"high": 0, "medium": 1, "low": 2}
    recs.sort(key=lambda r: priority_order.get(r.priority, 3))
    return recs


def format_recommendations_for_coze(recs: List[Recommendation]) -> str:
    """将建议格式化为Coze可直接使用的文本(供LLM润色参考)"""
    if not recs:
        return "当前数据暂不足以生成训练方案调整建议, 建议继续积累记录。"
    lines = []
    for i, r in enumerate(recs, 1):
        emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(r.priority, "⚪")
        lines.append(f"{emoji} 建议{i} [{r.priority.upper()}] {r.domain_name}")
        lines.append(f"   状态: {r.current_state}")
        lines.append(f"   行动: {r.action}")
        lines.append(f"   依据: {r.rationale}")
        lines.append("")
    return "\n".join(lines)