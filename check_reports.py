# -*- coding: utf-8 -*-
"""拉取两名儿童的纵向报告, 打印关键分析结果用于人工核对"""
import urllib.request, json

for cid, days in [("child_001", 90), ("child_002", 180)]:
    url = f"http://localhost:8000/api/report?child_id={cid}&period_days={days}"
    with urllib.request.urlopen(url) as r:
        resp = json.load(r)
    data = resp["data"]
    print(f"\n{'='*60}\n{cid} ({days}天, {data['total_sessions']}次训练)\n{'='*60}")
    print("[趋势]")
    for t in data["domain_trends"]:
        tag = "目标" if t["is_target"] else "问题"
        print(f"  {t['behavior_name']:8s}({tag}) 提及{t['total_mentions']:2d} 净分{t['net_score']:+6.1f} "
              f"斜率{t['trend_slope']:+.2f} {t['trend_label']:12s} 近2周{t['recent_score']:+.1f}")
    print("[异常预警]")
    for a in data["anomaly_alerts"]:
        print(f"  [{a['severity']}] {a['alert_type']}: {a['behavior_name']} - {a['description']}")
    if not data["anomaly_alerts"]:
        print("  (无)")
    print("[建议]")
    for r_ in data["recommendations"]:
        print(f"  [{r_['priority']}] {r_['domain_name']}: {r_['current_state']}")
    if not data["recommendations"]:
        print("  (无)")
    s = data["summary"]
    print(f"[摘要] {s['overall']}")
    for k in ("highlights", "concerns", "stagnations"):
        if s.get(k):
            print(f"  {k}: {'; '.join(s[k])}")