"""
演示种子数据生成器
生成2名儿童各6个月的模拟康复记录, 精心设计以展示:
- child_001(小明): 整体改善 + 指令跟随停滞(触发stagnation预警)
- child_002(小红): 先改善后退化 + 问题行为激增(触发regression/spike预警)

用法:
  python seed_data.py           # 直接运行
  或调用 POST /api/seed 接口
"""
import os
import sys
import random
from datetime import datetime, timedelta

# 兼容两种运行模式:
# 1. 开发模式: 从项目根目录运行, app包在当前目录
# 2. uvx安装模式: app包已安装到site-packages
try:
    from app import database as db
    from app.behavior_extractor import extract_behaviors
    from app.models import StoredRecord
except ImportError:
    # 开发模式兜底: 把项目根目录加入path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app import database as db
    from app.behavior_extractor import extract_behaviors
    from app.models import StoredRecord

random.seed(42)  # 固定随机种子, 保证每次生成一致

# ============================================================
# 儿童1: 小明 - 整体改善轨迹, 但指令跟随长期停滞
# ============================================================
CHILD_001_PHASES = {
    # 第1-8周: 基线期, 能力较低
    "early": [
        "今天小明眼神接触很少，基本不看人，叫他名字也没什么回应。刻板行为比较频繁，一直转圈和摇晃身体。",
        "个训课上小明不主动发起互动，都是老师先找他。指令跟随方面一步指令偶尔能照做，两步指令完全不行。刻板行为还是多，喜欢排列积木。",
        "今天试了模仿动作，小明还不能跟着做。眼神偶尔短暂对视一下马上移开。情绪还行，没有哭闹。",
        "小明今天主动看了一次老师，算是有进步。但指令跟随还是老样子，一步指令有时听懂有时不行。刻板行为频繁，一直拍手。",
    ],
    # 第9-18周: 改善期
    "improving": [
        "今天小明眼神接触有明显进步！主动看了老师好几次，目光对视时间比上周长了。刻板行为也减少了，只偶尔转圈。",
        "小明学会模仿简单动作了，跟着做拍手和摸头，很棒！指令跟随还是老样子，一步指令能照做，两步指令有时听懂有时不行。",
        "今天刻板行为明显减少，整节课只摇晃了两次。眼神接触持续进步，开始主动看老师了。情绪稳定。",
        "小明今天主动发起了互动，拿玩具给老师看，是很大的突破！模仿能力也在提升，能跟着做复杂一点的动作了。",
        "眼神接触继续进步，对视时间越来越长。刻板行为偶尔出现，频率低了很多。指令跟随维持原状，一步指令稳定，两步指令还是困难。",
    ],
    # 第19-26周: 持续改善+部分平台期
    "plateau_improving": [
        "小明这周表现不错，眼神接触保持得很好，经常主动持续对视。开始玩假装游戏了，给娃娃喂饭，是很大的进步！",
        "今天小明主动跟小朋友打招呼了，社交方面进步明显。游戏技能也在提升，能玩功能性游戏了。刻板行为极少。",
        "指令跟随还是和之前一样，一步指令能照做，两步指令有时听懂有时不行，感觉这块进展比较慢。眼神和游戏都继续进步。",
        "小明今天自己穿鞋了，自理能力有提升！眼神接触稳定，主动互动也多了。指令跟随维持，没有明显变化。",
        "今天做了配对分类练习，小明学会了颜色配对，认知方面有进步。眼神和社交保持良好。指令跟随还是老样子。",
        "小明开始玩合作游戏了，能和老师轮流搭积木，轮流互动有进步！眼神持续良好。指令跟随还是一步水平，没突破。",
    ],
}

# 每个阶段的周范围
CHILD_001_SCHEDULE = [
    ("early", 1, 8),
    ("improving", 9, 18),
    ("plateau_improving", 19, 26),
]

# ============================================================
# 儿童2: 小红 - 先改善后退化 + 问题行为激增
# ============================================================
CHILD_002_PHASES = {
    # 第1-10周: 基线期
    "early": [
        "小红今天无语言，偶尔发单音。共同注意没有反应，指东西给她看也不跟随。情绪爆发频繁，大哭了好几次。",
        "小红表达需求还是用手势和拉大人的手，没有口语。刻板行为多，一直旋转物品。今天又哭闹了，发脾气躺地上。",
        "今天小红偶尔说了一个单字，算是有一点进步。共同注意还是无反应。情绪爆发每周数次，尖叫比较严重。",
        "小红模仿能力不行，不能跟着做。刻板行为频繁，喜欢摇晃。情绪不太稳定，容易哭闹。",
    ],
    # 第11-20周: 显著改善期
    "improving": [
        "小红这周词汇使用进步很大！说了好几个新词，能说短语了，比如「要饼干」。共同注意也开始有反应，会跟随指向了。",
        "今天小红主动用口语表达需求了，说了「我要玩」，非常大的进步！情绪爆发明显减少，这周只哭了一次。",
        "小红学会模仿说话了，能跟着说短句。词汇量在增加，每天都在说新词。刻板行为也减少了。情绪稳定了很多。",
        "共同注意继续进步，小红今天主动指东西给我看了！词汇使用也在提升，能说三四个字的句子。情绪很好。",
        "小红今天自己洗手了，自理能力有提升！语言表达继续进步，会说「妈妈抱」。刻板行为偶尔，情绪稳定。",
    ],
    # 第21-26周: 退化期 + 问题行为激增
    "regression": [
        "最近小红词汇使用好像退步了，之前能说的句子现在不太愿意说了，表达需求又回到用手势拉人。有点担心。",
        "小红这两天刻板行为很频繁，一直转圈摇晃，比之前严重了。情绪爆发也变多了，大哭了好几次，尖叫失控。",
        "今天小红完全无法用口语表达，又回到之前的状态。情绪崩溃了两次，躺地上哭闹。刻板行为加重，一直旋转物品。",
        "小红最近不愿意说话了，叫她名字回应也变少了。情绪爆发频繁，几乎每天都有哭闹。刻板行为明显增加。",
        "今天情况没有好转，小红词汇使用继续退步，能说的词变少了。刻板行为频繁，情绪爆发严重，尖叫了很久。共同注意也不如之前了。",
        "小红这两天逃避行为也多了，不愿做任务就跑开。词汇使用还是退步状态。情绪爆发基本每天都有。刻板行为很频繁。",
    ],
}

CHILD_002_SCHEDULE = [
    ("early", 1, 10),
    ("improving", 11, 20),
    ("regression", 21, 26),
]


def _generate_records(child_id: str, phases: dict, schedule: list, therapist_id: str = "therapist_demo") -> list:
    """按周生成记录, 每周2次(周二/周五)"""
    records_data = []
    now = datetime.now()

    for phase_name, start_week, end_week in schedule:
        templates = phases[phase_name]
        for week in range(start_week, end_week + 1):
            # 计算该周的日期 (从26周前开始)
            days_ago = (26 - week) * 7
            week_start = now - timedelta(days=days_ago)
            # 周二和周五各一次
            for day_offset, template_idx_seed in [(0, week), (3, week + 13)]:
                session_date = week_start + timedelta(days=day_offset)
                if session_date > now:
                    continue
                # 从模板中选择 (确定性选择, 保证数据一致)
                template = templates[(template_idx_seed + week) % len(templates)]
                # 添加一点随机变化
                if random.random() > 0.5 and len(templates) > 1:
                    template = templates[(template_idx_seed + week + 1) % len(templates)]
                records_data.append({
                    "child_id": child_id,
                    "therapist_id": therapist_id,
                    "session_date": session_date.strftime("%Y-%m-%d"),
                    "content": template,
                    "session_type": "individual",
                    "duration_minutes": random.choice([30, 40, 45, 50, 60]),
                })
    return records_data


def seed_all() -> int:
    """灌入所有演示数据, 返回记录总数"""
    db.init_db()

    all_data = []
    all_data.extend(_generate_records("child_001", CHILD_001_PHASES, CHILD_001_SCHEDULE))
    all_data.extend(_generate_records("child_002", CHILD_002_PHASES, CHILD_002_SCHEDULE))

    count = 0
    for item in all_data:
        tags = extract_behaviors(item["content"])
        stored = StoredRecord(
            record_id=db.generate_record_id(),
            child_id=item["child_id"],
            therapist_id=item["therapist_id"],
            session_date=item["session_date"],
            content=item["content"],
            session_type=item["session_type"],
            duration_minutes=item["duration_minutes"],
            notes=None,
            behavior_tags=tags,
            created_at=db.now_str(),
        )
        db.save_record(stored)
        count += 1

    print(f"[seed] 共灌入 {count} 条演示记录")
    print(f"[seed] child_001(小明): 整体改善 + 指令跟随停滞")
    print(f"[seed] child_002(小红): 先改善后退化 + 问题行为激增")
    return count


if __name__ == "__main__":
    seed_all()