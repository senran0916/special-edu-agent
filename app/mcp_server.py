"""
MCP服务器 - 特殊教育康复决策智能体

为行云team智能体提供MCP工具(SSE模式):
- submit_record:   提交康复记录(自动提取行为标签)
- get_report:      获取完整纵向报告(趋势+异常+建议+摘要)
- analyze_child:   触发纵向分析(趋势+异常+建议)
- list_children:   列出所有有记录的儿童
- get_records:     查询儿童历史记录
- get_taxonomy:    查看行为分类体系

挂载在FastAPI应用的 /mcp 路径下, SSE端点为 /mcp/sse
"""
from typing import Optional

from mcp.server.mcpserver import MCPServer

from app import database as db
from app.models import StoredRecord
from app.behavior_extractor import extract_behaviors, extract_and_summarize, load_taxonomy
from app.longitudinal_analyzer import analyze_longitudinal, build_summary
from app.anomaly_detector import detect_anomalies
from app.recommendation_engine import generate_recommendations, format_recommendations_for_coze

mcp = MCPServer("special-edu-agent")


@mcp.tool()
def submit_record(
    child_id: str,
    session_date: str,
    content: str,
    session_type: str = "individual",
    duration_minutes: Optional[int] = None,
    notes: Optional[str] = None,
) -> dict:
    """提交一条康复训练记录, 自动提取行为标签并返回快速摘要。

    当康复师口述或输入一段训练记录文字时调用此工具。
    系统会自动从文字中识别出行为标签(如眼神接触、刻板行为等)及其方向(进步/退步/稳定)。

    Args:
        child_id: 儿童唯一标识, 如 child_001
        session_date: 训练日期, 格式 YYYY-MM-DD
        content: 康复师随手记录的原文(自然语言描述)
        session_type: 训练类型: individual(个训) 或 group(小组), 默认individual
        duration_minutes: 训练时长(分钟), 可选
        notes: 额外备注, 可选

    Returns:
        包含record_id、behavior_tags、quick_summary、domains_covered的结果
    """
    tags = extract_behaviors(content)

    stored = StoredRecord(
        record_id=db.generate_record_id(),
        child_id=child_id,
        therapist_id="mcp_user",
        session_date=session_date,
        content=content,
        session_type=session_type,
        duration_minutes=duration_minutes,
        notes=notes,
        behavior_tags=tags,
        created_at=db.now_str(),
    )
    db.save_record(stored)

    summary = extract_and_summarize(content)
    return {
        "success": True,
        "message": f"记录已保存, 提取到{len(tags)}个行为标签",
        "record_id": stored.record_id,
        "child_id": child_id,
        "session_date": session_date,
        "behavior_tags": [t.model_dump(mode="json") for t in tags],
        "quick_summary": summary["quick_summary"],
        "domains_covered": summary["domains_covered"],
    }


@mcp.tool()
def get_report(child_id: str, period_days: int = 90) -> dict:
    """获取儿童的完整纵向康复报告(趋势+异常预警+方案建议+整体摘要)。

    当用户要求查看某个孩子的阶段报告、康复进展总结、分析结果时调用此工具。
    这是最常用的工具, 一步到位返回所有分析结果。

    Args:
        child_id: 儿童唯一标识, 如 child_001
        period_days: 分析时间窗口(天), 默认90天(约3个月)

    Returns:
        完整报告: domain_trends(各行为趋势)、anomaly_alerts(异常预警)、
        recommendations(方案建议)、summary(整体摘要)
    """
    records = db.get_records_by_child(child_id, days=period_days)
    if not records:
        return {
            "success": False,
            "message": f"儿童 {child_id} 在{period_days}天内无记录, 请先提交康复记录",
        }

    trends = analyze_longitudinal(records, period_days)
    alerts = detect_anomalies(trends)
    recs = generate_recommendations(trends, alerts)
    summary = build_summary(trends)

    return {
        "success": True,
        "child_id": child_id,
        "period_days": period_days,
        "total_sessions": len(records),
        "domain_trends": [t.model_dump(mode="json") for t in trends],
        "anomaly_alerts": [a.model_dump(mode="json") for a in alerts],
        "recommendations": [r.model_dump(mode="json") for r in recs],
        "recommendations_text": format_recommendations_for_coze(recs),
        "summary": summary,
    }


@mcp.tool()
def analyze_child(child_id: str, period_days: int = 90) -> dict:
    """对儿童的历史记录进行纵向分析(趋势+异常+建议)。

    与get_report类似, 但不包含整体摘要, 适合只需要原始分析数据的场景。

    Args:
        child_id: 儿童唯一标识
        period_days: 分析时间窗口(天), 默认90天

    Returns:
        分析结果: domain_trends、anomaly_alerts、recommendations
    """
    records = db.get_records_by_child(child_id, days=period_days)
    if not records:
        return {
            "success": False,
            "message": f"儿童 {child_id} 在{period_days}天内无记录",
        }

    trends = analyze_longitudinal(records, period_days)
    alerts = detect_anomalies(trends)
    recs = generate_recommendations(trends, alerts)

    return {
        "success": True,
        "child_id": child_id,
        "period_days": period_days,
        "total_sessions": len(records),
        "domain_trends": [t.model_dump(mode="json") for t in trends],
        "anomaly_alerts": [a.model_dump(mode="json") for a in alerts],
        "recommendations": [r.model_dump(mode="json") for r in recs],
    }


@mcp.tool()
def list_children() -> dict:
    """列出系统中有康复记录的所有儿童。

    当用户询问有哪些孩子、想查看某个孩子但不知道ID时调用此工具。

    Returns:
        儿童列表, 每个包含child_id、session_count(训练次数)、first_session、last_session
    """
    children = db.list_children()
    return {
        "success": True,
        "total": len(children),
        "children": children,
    }


@mcp.tool()
def get_records(child_id: str, days: Optional[int] = None) -> dict:
    """查询儿童的历史康复记录。

    当用户想翻看某个孩子之前的训练记录内容时调用此工具。

    Args:
        child_id: 儿童唯一标识
        days: 最近N天的记录, 不填则返回全部历史

    Returns:
        记录列表, 每条包含content(原文)、behavior_tags(行为标签)、session_date等
    """
    records = db.get_records_by_child(child_id, days=days)
    return {
        "success": True,
        "child_id": child_id,
        "total": len(records),
        "records": [r.model_dump(mode="json") for r in records],
    }


@mcp.tool()
def get_taxonomy() -> dict:
    """查看行为分类体系(6大领域19个行为)。

    当用户想了解系统能识别哪些行为、有哪些评估维度时调用此工具。
    包含: 社交沟通、语言表达、语言理解、行为问题、生活自理、认知学习。

    Returns:
        分类体系: 所有领域及其下的行为列表
    """
    taxonomy = load_taxonomy()
    return {
        "success": True,
        "version": taxonomy["version"],
        "description": taxonomy["description"],
        "domains": [
            {
                "id": d["id"],
                "name": d["name"],
                "is_target": d["is_target"],
                "behaviors": [
                    {"id": b["id"], "name": b["name"]}
                    for b in d["behaviors"]
                ],
            }
            for d in taxonomy["domains"]
        ],
    }


def main():
    """stdio模式入口 - 供uvx/行云MCP配置调用

    行云MCP配置JSON:
    {
      "mcpServers": {
        "special-edu-agent": {
          "command": "uvx",
          "args": ["--from", "git+https://github.com/senran0916/special-edu-agent.git", "special-edu-mcp"]
        }
      }
    }
    """
    # stdio模式: 初始化数据库并灌入演示数据
    db.init_db()
    try:
        if db.count_records() == 0:
            from app.seed_data import seed_all
            n = seed_all()
            print(f"[mcp-stdio] 检测到空库, 已自动灌入演示数据 {n} 条", file=sys.stderr)
    except Exception as e:
        print(f"[mcp-stdio] 自动灌入演示数据失败: {e}", file=sys.stderr)

    # 以stdio模式运行MCP服务器
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()