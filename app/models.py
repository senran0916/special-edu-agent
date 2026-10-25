"""
数据模型定义 - Pydantic schemas
用于API请求/响应校验和内部数据流转
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum


class Direction(str, Enum):
    """行为方向: 正向(进步)/负向(退步)/中性(稳定)"""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class BehaviorTag(BaseModel):
    """从记录中提取的结构化行为标签"""
    behavior_id: str = Field(..., description="行为ID, 如 eye_contact")
    behavior_name: str = Field(..., description="行为名称, 如 眼神接触")
    domain_id: str = Field(..., description="领域ID, 如 social_communication")
    domain_name: str = Field(..., description="领域名称, 如 社交沟通")
    direction: Direction = Field(..., description="方向: positive/negative/neutral")
    score: float = Field(0.0, description="该条记录对该行为的评分: +1/-1/0")
    matched_keywords: List[str] = Field(default_factory=list, description="匹配到的关键词")
    evidence: str = Field("", description="原文中的证据片段")
    level_hint: Optional[str] = Field(None, description="推断的能力等级")


class SessionRecord(BaseModel):
    """单次康复训练记录(用户输入)"""
    child_id: str = Field(..., description="儿童唯一标识")
    therapist_id: str = Field(default="anonymous", description="康复师标识")
    session_date: str = Field(..., description="训练日期 YYYY-MM-DD")
    content: str = Field(..., description="康复师随手记录的原文")
    session_type: str = Field(default="individual", description="训练类型: individual/group")
    duration_minutes: Optional[int] = Field(None, description="训练时长(分钟)")
    notes: Optional[str] = Field(None, description="额外备注")


class StoredRecord(BaseModel):
    """数据库中存储的完整记录(含提取结果)"""
    record_id: str
    child_id: str
    therapist_id: str
    session_date: str
    content: str
    session_type: str
    duration_minutes: Optional[int] = None
    notes: Optional[str] = None
    behavior_tags: List[BehaviorTag] = []
    created_at: str


class DomainTrend(BaseModel):
    """单个领域/行为的纵向趋势"""
    domain_id: str
    domain_name: str
    behavior_id: str
    behavior_name: str
    is_target: bool = Field(..., description="是否为目标行为( True=希望提升, False=希望减少)")
    total_mentions: int = Field(0, description="总提及次数")
    positive_count: int = Field(0, description="正向提及次数")
    negative_count: int = Field(0, description="负向提及次数")
    net_score: float = Field(0.0, description="净得分 = positive - negative")
    trend_slope: float = Field(0.0, description="线性趋势斜率(正=向好, 负=向差)")
    trend_label: str = Field("stable", description="趋势标签: improving/stable/declining")
    recent_score: float = Field(0.0, description="最近2周净得分")
    previous_score: float = Field(0.0, description="之前2周净得分")
    period_change: float = Field(0.0, description="近期变化 = recent - previous")


class AnomalyAlert(BaseModel):
    """异常预警"""
    alert_type: str = Field(..., description="类型: regression/stagnation/spike")
    severity: str = Field(..., description="严重度: high/medium/low")
    domain_id: str
    domain_name: str
    behavior_id: str
    behavior_name: str
    description: str = Field(..., description="异常描述")
    evidence: str = Field("", description="数据依据")
    suggestion: str = Field("", description="初步建议")


class Recommendation(BaseModel):
    """训练方案调整建议"""
    priority: str = Field(..., description="优先级: high/medium/low")
    domain_id: str
    domain_name: str
    current_state: str = Field(..., description="当前状态描述")
    action: str = Field(..., description="建议采取的行动")
    rationale: str = Field(..., description="建议依据")
    target_behaviors: List[str] = Field(default_factory=list)


class LongitudinalReport(BaseModel):
    """纵向分析完整报告(返回给Coze)"""
    child_id: str
    report_date: str
    period_days: int = Field(..., description="分析覆盖天数")
    total_sessions: int = Field(0, description="总训练次数")
    domain_trends: List[DomainTrend] = Field(default_factory=list)
    anomaly_alerts: List[AnomalyAlert] = Field(default_factory=list)
    recommendations: List[Recommendation] = Field(default_factory=list)
    summary: Dict = Field(default_factory=dict, description="整体摘要: 亮点/关注点/总体评价")
    disclaimer: str = Field(
        "本报告由AI辅助生成, 仅供康复师参考, 不构成医疗诊断。"
        "所有训练方案调整请结合专业评估和临床判断。",
        description="免责声明"
    )


class AnalyzeRequest(BaseModel):
    """触发分析的请求"""
    child_id: str = Field(..., description="儿童ID")
    period_days: int = Field(90, description="分析时间窗口(天), 默认90天")


class APIResponse(BaseModel):
    """统一响应格式"""
    success: bool = True
    message: str = "ok"
    data: Optional[dict] = None