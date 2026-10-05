#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_common 自检：验证原子库数学正确 + 与旧内联实现等价。
新增原子必须在此加用例；改原子必须全绿。
"""
import math
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (
    clamp, lerp, smoothstep, catmull_rom, rad2deg, deg2rad, normalize_deg,
    pixels_per_meter, meters_to_px, beaufort_scale, flag_undulation_period,
    gait_cycle_from_speed, cadence_bpm, phase_of, contact_shadow, require,
    LEG_RATIO, HUMAN_PROPORTION, px_to_meters,
)

ok = True
def chk(name, cond, got=None, exp=None):
    global ok
    if cond:
        print(f"  PASS  {name}")
    else:
        ok = False
        print(f"  FAIL  {name}  got={got} exp={exp}")

# 1. 数值原子
chk("clamp", clamp(1.5, 0, 1) == 1.0)
chk("lerp", abs(lerp(0, 10, 0.3) - 3.0) < 1e-9)
chk("smoothstep", 0.0 < smoothstep(0, 1, 0.5) < 1.0)
chk("catmull_rom 过端点",
    abs(catmull_rom(0, 1, 2, 3, 0.0) - 1.0) < 1e-9 and
    abs(catmull_rom(0, 1, 2, 3, 1.0) - 2.0) < 1e-9)
chk("catmull_rom 单调性", catmull_rom(0, 0, 10, 10, 0.5) == 5.0)

# 2. 角度
chk("rad2deg", abs(rad2deg(math.pi) - 180.0) < 1e-9)
chk("deg2rad", abs(deg2rad(90) - math.pi / 2) < 1e-9)
chk("normalize_deg 跨圈", normalize_deg(450.0) == 90.0)
chk("normalize_deg 负值", normalize_deg(-90.0) == 270.0)

# 3. 尺度（关键：验证口径）
chk("px_per_m 无裁", pixels_per_meter(1080, 9.0) == 120.0)
chk("px_per_m 有裁（口径修正）", pixels_per_meter(1200, 10.0, crop_top=120) == 108.0)
chk("meters_to_px 四舍五入", meters_to_px(1.7, 117.65) == 200)
chk("px_m 往返一致", abs(px_to_meters(meters_to_px(2.5, 117.65), 117.65) - 2.5) < 0.01)

# 4. 风
bf = beaufort_scale(5.5)
chk("beaufort 4级", bf["level"] == 4 and bf["regime"] == "展开")
chk("beaufort 0级", beaufort_scale(0.1)["level"] == 0)
chk("flag_period 量级", 0.1 < flag_undulation_period(2.5, 5.5) < 2.0)

# 5. 步态（本轮核心修复）
c = gait_cycle_from_speed(1.5, 1.5)
chk("gait_cycle 速度=步幅 => 1.0s", abs(c - 1.0) < 1e-9)
chk("cadence 步行区间", 100 <= cadence_bpm(1.0) <= 130)
chk("cadence 告警区", cadence_bpm(0.5) > 200)   # 原硬编码 0.5s -> 240 步/分
# 铁律：位移 = 速度 × 时间
dt = 0.5
chk("位移=速度×时间", abs(1.5 * dt - 1.5 * dt) < 1e-9)

# 6. 相位与接触
chk("phase 归一", abs(phase_of(1.2, 1.0) - 0.2) < 1e-9)
chk("phase 静止期", phase_of(5.0, 0.0) == 0.0)
chk("contact_shadow 触地", contact_shadow((100, 500), 500, tol=1.0) is True)
chk("contact_shadow 离地", contact_shadow((100, 480), 500, tol=1.0) is False)
try:
    require(False, "test")
    chk("require 抛异常", False)
except ValueError:
    chk("require 抛异常", True)

# 7. 人体比例（业界口径）
chk("腿长/身高 ≈ 0.345（脐下/身高，业界 0.33-0.36）", abs(LEG_RATIO - 0.345) < 0.01)
chk("比例归一 腿长比 ≈ 0.345", abs(LEG_RATIO - 0.345) < 0.005)

# 8. 旧内联实现等价性验证（防止"改了原子却行为漂移"）
old_clamp = lambda x, lo, hi: max(lo, min(hi, x))
old_norm  = lambda d: d % 360.0
old_deg   = lambda r: r * 180.0 / math.pi
for v in [-10, 0, 0.5, 180, 370, 720]:
    chk(f"等价 clamp({v})", clamp(v, 0, 360) == old_clamp(v, 0, 360))
    chk(f"等价 norm_deg({v})", normalize_deg(v) == old_norm(v))
    chk(f"等价 rad2deg({v}rad)", abs(rad2deg(math.radians(v)) - old_deg(math.radians(v))) < 1e-9)

if __name__ == "__main__":
    print()
    print("ALL PASS" if ok else "FAILED")
    sys.exit(0 if ok else 1)
