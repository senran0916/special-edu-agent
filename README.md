---
title: 特殊教育康复决策智能体
emoji: 🎓
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# 特殊教育康复决策智能体 - 后端API

为Coze智能体提供**行为标签提取、纵向时序分析、异常预警、训练方案推荐**能力。

## 核心价值

不是"记录整理工具"，而是**纵向行为演化分析引擎**：
- 对比3个月前 vs 现在，识别行为趋势（改善/停滞/退化）
- 自动检测异常（行为退化、干预停滞、问题行为激增）
- 基于数据给出训练方案调整建议（不是泛泛而谈，而是有数据依据的具体行动）

## 快速开始（本地）

```bash
cd special-edu-agent
pip install -r requirements.txt

# 灌入演示数据
python seed_data.py

# 启动服务
python -m app.main
# 或: uvicorn app.main:app --host 0.0.0.0 --port 8000
```

访问 http://localhost:8000/docs 查看交互式API文档。

## 部署到Render（免费，无需服务器）

### 方式一：GitHub + Render（推荐）

1. 将本项目推送到GitHub仓库
2. 登录 https://render.com → New → Web Service
3. 连接GitHub仓库，Render会自动识别 `render.yaml`
4. 点击Create，等待部署完成（约2-3分钟）
5. 部署完成后获得地址，如 `https://special-edu-agent.onrender.com`

### 方式二：命令行

```bash
# 安装Render CLI后
render deploy
```

### 部署后必须做

部署完成后，调用一次灌入演示数据：
```bash
curl -X POST https://你的地址.onrender.com/api/seed
```

> ⚠️ Render免费版重启后数据会清空（SQLite是临时存储），重启后需重新调用 `/api/seed`。正式产品应换用PostgreSQL（Render免费提供）。

## API接口文档

### 1. 提交康复记录
```
POST /api/records
```
```json
{
  "child_id": "child_001",
  "session_date": "2026-10-25",
  "content": "今天小明眼神接触有明显进步，主动看了老师好几次。刻板行为还是频繁，一直转圈。",
  "session_type": "individual",
  "duration_minutes": 45
}
```
返回：自动提取的行为标签 + 快速摘要

### 2. 获取完整报告（Coze最常用）
```
GET /api/report?child_id=child_001&period_days=90
```
返回：趋势分析 + 异常预警 + 方案建议 + 整体摘要

### 3. 触发分析
```
POST /api/analyze
```
```json
{ "child_id": "child_001", "period_days": 90 }
```

### 4. 查询历史记录
```
GET /api/records?child_id=child_001&days=90
```

### 5. 其他
- `GET /api/children` - 列出所有儿童
- `GET /api/taxonomy` - 查看行为分类体系
- `POST /api/seed` - 一键灌入演示数据
- `GET /api/health` - 健康检查

## Coze接入方法

### 第1步：创建插件
1. Coze → 插件 → 创建插件 → 选择"基于API"
2. 填入你的Render地址，如 `https://special-edu-agent.onrender.com`
3. 导入以下接口：
   - `POST /api/records`（提交记录）
   - `GET /api/report`（获取报告）
   - `POST /api/analyze`（触发分析）

### 第2步：搭建工作流
```
用户输入记录
  → 调用 POST /api/records（提取行为标签）
  → 展示快速摘要
  → 用户要求阶段报告时
  → 调用 GET /api/report
  → LLM节点将JSON润色为温暖的康复小结
  → 输出报告
```

### 第3步：LLM润色Prompt参考
```
你是一位资深特殊教育康复顾问。请将以下数据分析结果，
转化为一份温暖、专业、可执行的阶段性康复小结。

要求：
1. 用鼓励性的语言描述进步
2. 明确指出需要关注的异常，但不制造焦虑
3. 将建议转化为具体、可操作的本周行动项
4. 结尾附上免责声明

数据分析结果：
{{report_json}}
```

## 演示数据说明

内置2名儿童的6个月模拟数据：

| 儿童 | 轨迹设计 | 展示的分析能力 |
|------|----------|----------------|
| child_001 小明 | 整体改善 + 指令跟随停滞 | 趋势识别 + 停滞预警 |
| child_002 小红 | 先改善后退化 + 问题行为激增 | 退化预警 + 激增预警 |

## 项目结构

```
special-edu-agent/
├── app/
│   ├── main.py                  # FastAPI入口
│   ├── models.py                # Pydantic数据模型
│   ├── database.py              # SQLite数据层
│   ├── behavior_extractor.py    # 行为标签提取引擎
│   ├── longitudinal_analyzer.py # 纵向时序分析
│   ├── anomaly_detector.py      # 异常检测
│   └── recommendation_engine.py # 方案推荐
├── data/
│   ├── taxonomy.json            # 行为分类体系(6领域19行为)
│   └── records.db               # SQLite数据库(运行时生成)
├── seed_data.py                 # 演示数据生成器
├── requirements.txt
├── Dockerfile
├── render.yaml                  # Render部署配置
└── README.md
```

## 技术说明

- **行为提取**：基于taxonomy的关键词匹配 + 方向词检测，无需外部LLM API（LLM润色由Coze侧完成）
- **趋势分析**：按周聚合得分 + 最小二乘线性回归斜率
- **异常检测**：规则引擎（退化/停滞/激增三类规则）
- **方案推荐**：优先级规则引擎（先处理高危异常，再调整停滞领域，最后进阶优势领域）

## 免责声明

本系统仅辅助康复师进行数据分析和方案参考，不构成医疗诊断。所有训练方案调整需结合专业评估和临床判断。