# -*- coding: utf-8 -*-
"""快速验证方向词评分修复: 关键句子的预期极性"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.behavior_extractor import extract_behaviors

# (句子, 预期行为名, 预期方向)
CASES = [
    # 问题行为 + 减少 => 应为 positive (问题减轻=好事) [修复前是 negative, 错]
    ("今天刻板行为明显减少，整节课只摇晃了两次。", "刻板行为", "positive"),
    ("情绪爆发明显减少，这周只哭了一次。", "情绪爆发", "positive"),
    # 问题行为 + 增加/频繁/加重 => 应为 negative [修复前"增加"是 positive, 错]
    ("刻板行为明显增加，比之前严重了。", "刻板行为", "negative"),
    ("情绪爆发频繁，几乎每天都有哭闹。", "情绪爆发", "negative"),
    # 目标行为 + 增加/进步 => positive
    ("小红词汇量在增加，每天都在说新词。", "词汇使用", "positive"),
    ("眼神接触有明显进步！主动看了老师好几次。", "眼神接触", "positive"),
    # 目标行为 + 退步 => negative
    ("小红词汇使用好像退步了，之前能说的句子现在不太愿意说了。", "词汇使用", "negative"),
    # "不能"不应被其中的"能"抵消 => negative
    ("今天试了模仿动作，小明还不能跟着做。", "模仿能力", "negative"),
    # "能照做"无变化词 => neutral (移除噪声词"能"后的预期行为)
    ("指令跟随维持原状，一步指令能照做。", "指令跟随", "neutral"),
    # "不行" => negative [新增词]
    ("两步指令完全不行。", "指令跟随", "negative"),
    # "不主动" => negative [新增词]
    ("个训课上小明不主动发起互动，都是老师先找他。", "主动发起互动", "negative"),
]

passed = failed = 0
for sentence, behavior_name, expected in CASES:
    tags = extract_behaviors(sentence)
    tag = next((t for t in tags if t.behavior_name == behavior_name), None)
    if tag is None:
        print(f"[FAIL] 未提取到「{behavior_name}」: {sentence}")
        failed += 1
        continue
    actual = tag.direction.value
    mark = "OK  " if actual == expected else "FAIL"
    if actual == expected:
        passed += 1
    else:
        failed += 1
    print(f"[{mark}] {behavior_name}: 期望={expected} 实际={actual} 得分={tag.score:+.0f} | {sentence}")

print(f"\n结果: {passed} 通过 / {failed} 失败")
sys.exit(1 if failed else 0)