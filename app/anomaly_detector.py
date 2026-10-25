"""
异常检测模块
基于纵向趋势数据识别三类异常:
1. regression (行为退化): 曾在改善, 近期明显下滑
2. stagnation (干预停滞): 目标行为长期无变化且水平偏低
3. spike (问题行为激增): 问题行为近期突然加重
"""
from typing import List
from app.models import DomainTrend, AnomalyAlert


def detect_anomalies(trends: List[DomainTrend]) -> List[AnomalyAlert]:
    """检测行为异常并生成预警

    Args:
        trends: 纵向分析输出的趋势列表

    Returns:
        异常预警列表, 按严重度排序
    """
    alerts = []

    for t in trends:
        # ---- 1. 行为退化检测 ----
        # 条件: 整体斜率为正(曾在改善), 但近期得分比前期明显下降
        if (
            t.trend_slope > 0.1
            and t.period_change < -1.0
            and t.total_mentions >= 3
        ):
            severity = "high" if t.period_change < -2.0 else "medium"
            alerts.append(AnomalyAlert(
                alert_type="regression",
                severity=severity,
                domain_id=t.domain_id,
                domain_name=t.domain_name,
                behavior_id=t.behavior_id,
                behavior_name=t.behavior_name,
                description=(
                    f"{t.behavior_name}此前呈改善趋势, 但近2周出现明显回落"
                    f"(前期{t.previous_score:+.1f} → 近期{t.recent_score:+.1f})。"
                ),
                evidence=(
                    f"整体斜率{t.trend_slope:+.2f}, 近期变化{t.period_change:+.1f}, "
                    f"累计提及{t.total_mentions}次。"
                ),
                suggestion=(
                    "建议排查近期环境/人员/routine是否有变化; "
                    "适当降低任务难度, 回归已掌握的技能重建成功体验, 再逐步提升要求。"
                ),
            ))

        # ---- 2. 干预停滞检测 ----
        # 条件: 目标行为, 提及次数充足(>=4), 斜率接近0, 且净得分<=0
        if (
            t.is_target
            and t.total_mentions >= 4
            and abs(t.trend_slope) <= 0.1
            and t.net_score <= 0
            and t.trend_label == "stable"
        ):
            alerts.append(AnomalyAlert(
                alert_type="stagnation",
                severity="medium",
                domain_id=t.domain_id,
                domain_name=t.domain_name,
                behavior_id=t.behavior_id,
                behavior_name=t.behavior_name,
                description=(
                    f"{t.behavior_name}在观察期内长期停滞"
                    f"(提及{t.total_mentions}次, 净得分{t.net_score:+.1f}, 无明显趋势)。"
                ),
                evidence=(
                    f"斜率{t.trend_slope:+.2f}, 正向{t.positive_count}次 / "
                    f"负向{t.negative_count}次。"
                ),
                suggestion=(
                    "当前干预策略可能已进入平台期。建议: "
                    "1)更换教学材料或强化物, 提升动机; "
                    "2)尝试将技能拆解为更小的步骤; "
                    "3)增加该领域的训练频次或变换训练场景(泛化)。"
                ),
            ))

        # ---- 3. 问题行为激增检测 ----
        # 条件: 非目标行为(问题行为), 近期得分比前期明显更负
        if (
            not t.is_target
            and t.total_mentions >= 3
            and t.recent_score < -1.0
            and t.period_change < -1.0
        ):
            severity = "high" if t.recent_score < -3.0 else "medium"
            alerts.append(AnomalyAlert(
                alert_type="spike",
                severity=severity,
                domain_id=t.domain_id,
                domain_name=t.domain_name,
                behavior_id=t.behavior_id,
                behavior_name=t.behavior_name,
                description=(
                    f"问题行为「{t.behavior_name}」近期明显加重"
                    f"(前期{t.previous_score:+.1f} → 近期{t.recent_score:+.1f})。"
                ),
                evidence=(
                    f"近期变化{t.period_change:+.1f}, 累计负向提及{t.negative_count}次。"
                ),
                suggestion=(
                    "建议尽快进行功能行为评估(FBA), 识别该行为的动机"
                    "(获取关注/逃避任务/感官刺激/获取物品), "
                    "并据此调整前事策略与替代行为教学。"
                ),
            ))

        # ---- 4. 问题行为持续高位 ----
        # 条件: 非目标行为, 净得分很负, 持续存在
        if (
            not t.is_target
            and t.net_score <= -3.0
            and t.total_mentions >= 5
            and t.trend_label != "improving"
        ):
            # 避免与spike重复
            already_alerted = any(
                a.behavior_id == t.behavior_id and a.alert_type == "spike"
                for a in alerts
            )
            if not already_alerted:
                alerts.append(AnomalyAlert(
                    alert_type="spike",
                    severity="low",
                    domain_id=t.domain_id,
                    domain_name=t.domain_name,
                    behavior_id=t.behavior_id,
                    behavior_name=t.behavior_name,
                    description=(
                        f"问题行为「{t.behavior_name}」持续处于较高水平"
                        f"(净得分{t.net_score:+.1f}), 未见明显改善。"
                    ),
                    evidence=f"累计提及{t.total_mentions}次, 负向{t.negative_count}次。",
                    suggestion=(
                        "该行为已成为稳定模式, 建议系统性地制定行为干预计划(BIP), "
                        "并确保所有干预人员执行策略一致。"
                    ),
                ))

    # 按严重度排序: high > medium > low
    severity_order = {"high": 0, "medium": 1, "low": 2}
    alerts.sort(key=lambda a: severity_order.get(a.severity, 3))
    return alerts