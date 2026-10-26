"""
FastAPI入口 - 特殊教育康复决策智能体后端API

供Coze自定义插件调用的核心接口:
- POST /api/records          提交康复记录(自动提取行为标签)
- GET  /api/records          查询历史记录
- POST /api/analyze          触发纵向分析(趋势+异常+建议)
- GET  /api/report           获取完整报告(一步到位, Coze最常用)
- GET  /api/children         列出所有儿童(demo用)
- POST /api/seed             一键灌入演示数据(demo用)
- GET  /api/health           健康检查
- GET  /api/taxonomy         查看行为分类体系
"""
import os
import sys

# 确保项目根目录在path中, 支持直接 python -m app.main 运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from typing import Optional

from app import database as db
from app.models import (
    SessionRecord,
    StoredRecord,
    AnalyzeRequest,
    APIResponse,
    LongitudinalReport,
)
from app.behavior_extractor import extract_behaviors, extract_and_summarize, load_taxonomy
from app.longitudinal_analyzer import analyze_longitudinal, build_summary
from app.anomaly_detector import detect_anomalies
from app.recommendation_engine import generate_recommendations, format_recommendations_for_coze

app = FastAPI(
    title="特殊教育康复决策智能体 API",
    description="为Coze智能体提供行为提取、纵向分析、异常预警与方案推荐能力",
    version="1.0.0",
)

# 允许Coze跨域调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    """启动时初始化数据库; 若为空库则自动灌入演示数据

    行云容器重启后SQLite数据会丢失, 自动灌入保证服务开箱即用。
    """
    db.init_db()
    try:
        if db.count_records() == 0:
            from seed_data import seed_all
            n = seed_all()
            print(f"[startup] 检测到空库, 已自动灌入演示数据 {n} 条")
    except Exception as e:
        print(f"[startup] 自动灌入演示数据失败(不影响服务运行): {e}")


# ==================== 核心接口 ====================

@app.post("/api/records", response_model=APIResponse)
def submit_record(record: SessionRecord):
    """提交一条康复训练记录

    自动执行行为标签提取, 并将结构化结果一并存储。
    返回提取结果供Coze即时展示。
    """
    # 提取行为标签
    tags = extract_behaviors(record.content)

    stored = StoredRecord(
        record_id=db.generate_record_id(),
        child_id=record.child_id,
        therapist_id=record.therapist_id,
        session_date=record.session_date,
        content=record.content,
        session_type=record.session_type,
        duration_minutes=record.duration_minutes,
        notes=record.notes,
        behavior_tags=tags,
        created_at=db.now_str(),
    )
    db.save_record(stored)

    summary = extract_and_summarize(record.content)
    return APIResponse(
        success=True,
        message=f"记录已保存, 提取到{len(tags)}个行为标签",
        data={
            "record_id": stored.record_id,
            "child_id": stored.child_id,
            "session_date": stored.session_date,
            "behavior_tags": [t.model_dump(mode="json") for t in tags],
            "quick_summary": summary["quick_summary"],
            "domains_covered": summary["domains_covered"],
        },
    )


@app.get("/api/records", response_model=APIResponse)
def get_records(
    child_id: str = Query(..., description="儿童ID"),
    days: Optional[int] = Query(None, description="最近N天"),
):
    """查询儿童的历史记录"""
    records = db.get_records_by_child(child_id, days=days)
    return APIResponse(
        success=True,
        message=f"找到{len(records)}条记录",
        data={
            "child_id": child_id,
            "total": len(records),
            "records": [r.model_dump(mode="json") for r in records],
        },
    )


@app.post("/api/analyze", response_model=APIResponse)
def analyze(request: AnalyzeRequest):
    """触发纵向分析: 趋势 + 异常 + 建议"""
    records = db.get_records_by_child(request.child_id, days=request.period_days)
    if not records:
        return APIResponse(
            success=False,
            message=f"儿童 {request.child_id} 在{request.period_days}天内无记录",
            data=None,
        )

    trends = analyze_longitudinal(records, request.period_days)
    alerts = detect_anomalies(trends)
    recs = generate_recommendations(trends, alerts)

    return APIResponse(
        success=True,
        message="分析完成",
        data={
            "child_id": request.child_id,
            "period_days": request.period_days,
            "total_sessions": len(records),
            "domain_trends": [t.model_dump(mode="json") for t in trends],
            "anomaly_alerts": [a.model_dump(mode="json") for a in alerts],
            "recommendations": [r.model_dump(mode="json") for r in recs],
            "recommendations_text": format_recommendations_for_coze(recs),
        },
    )


@app.get("/api/report", response_model=APIResponse)
def get_report(
    child_id: str = Query(..., description="儿童ID"),
    period_days: int = Query(90, description="分析窗口(天)"),
):
    """获取完整纵向报告(Coze最常用的接口)

    一步到位返回: 趋势 + 异常 + 建议 + 摘要, Coze的LLM节点
    直接消费此结果润色成康复小结。
    """
    records = db.get_records_by_child(child_id, days=period_days)
    if not records:
        return APIResponse(
            success=False,
            message=f"儿童 {child_id} 在{period_days}天内无记录, 请先提交康复记录",
            data=None,
        )

    trends = analyze_longitudinal(records, period_days)
    alerts = detect_anomalies(trends)
    recs = generate_recommendations(trends, alerts)
    summary = build_summary(trends)

    report = LongitudinalReport(
        child_id=child_id,
        report_date=datetime.now().strftime("%Y-%m-%d"),
        period_days=period_days,
        total_sessions=len(records),
        domain_trends=trends,
        anomaly_alerts=alerts,
        recommendations=recs,
        summary=summary,
    )

    return APIResponse(
        success=True,
        message="报告生成完成",
        data=report.model_dump(mode="json"),
    )


# ==================== 辅助接口 ====================

@app.get("/api/children", response_model=APIResponse)
def list_children():
    """列出所有有记录的儿童(demo/调试用)"""
    children = db.list_children()
    return APIResponse(
        success=True,
        message=f"共{len(children)}名儿童",
        data={"children": children},
    )


@app.get("/api/taxonomy", response_model=APIResponse)
def get_taxonomy():
    """查看行为分类体系"""
    taxonomy = load_taxonomy()
    return APIResponse(
        success=True,
        message="ok",
        data={
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
        },
    )


@app.post("/api/seed", response_model=APIResponse)
def seed_demo_data():
    """一键灌入演示数据(demo用, 生成一个孩子6个月的模拟记录)"""
    try:
        from seed_data import seed_all
        count = seed_all()
        return APIResponse(
            success=True,
            message=f"演示数据灌入成功, 共{count}条记录",
            data={"record_count": count},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"灌入失败: {str(e)}")


@app.get("/api/health")
def health_check():
    """健康检查(部署平台探活用)"""
    return {"status": "ok", "service": "special-edu-agent", "time": datetime.now().isoformat()}


@app.get("/")
def root():
    """根路径 - 服务信息"""
    return {
        "service": "特殊教育康复决策智能体 API",
        "docs": "/docs",
        "health": "/api/health",
        "endpoints": [
            "POST /api/records - 提交康复记录",
            "GET  /api/records - 查询历史记录",
            "POST /api/analyze - 触发纵向分析",
            "GET  /api/report  - 获取完整报告",
            "GET  /api/children - 列出儿童",
            "POST /api/seed    - 灌入演示数据",
        ],
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))  # 行云仅暴露8080, 本地默认保持一致
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)