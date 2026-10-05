"""审计：从 SHOTS 推导需要哪些 actor、什么动作，代码能否供给"""
import re, json
import character_sheet as cs

# 当前能力池（代码能驱动的）
CAP = {
    "stand": "静立", "walk": "8帧走路", "kneel": "跪",
    "detail": "局部特写", "sit": "坐(缺)", "lie": "躺(缺)",
    "grow": "生长(缺)", "swim": "游(缺)", "fly": "飞(缺)",
}

src = open("render_v4.py", encoding="utf-8").read()
shots = re.findall(r'name:\s*"([^"]+)".*?bg:\s*"([^"]+)".*?caption:\s*"([^"]*)"',
                   src, re.S)
print("=" * 66)
print("当前 SHOTS 的 actor 需求推导")
print("=" * 66)
for nm, bg, cap in shots:
    print(f"  {nm:12s} bg={bg:8s} {cap[:22]}")
print()
print("=" * 66)
print("代码能力池 vs 需求")
print("=" * 66)
for k, v in CAP.items():
    has = "(缺)" in v
    print(f"  {k:8s} {v:10s} {'不可供给' if has else '可供给'}")
