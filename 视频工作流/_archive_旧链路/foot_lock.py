#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""足锁：接触时锁定脚的世界坐标，切换用三次惯性化平滑。

X_a：从 pose.py 拆出（pose.py 加本模块后 349 行/12939 字符，超阈值
400/12000，按铁律必须拆分而非提阈值）。

业界要点（theorangeduck / UE）:
  1) 接触开始时锁定该帧脚在世界坐标的位置，支撑期内恒定 —— 灭 foot sliding。
     （pose.foot_target 的 stance 分支已返回恒定的 (x0, ankle)）
  2) lock/unlock 切换不能硬跳：用三次惯性化 cubic inertialization 平滑，
     保证速度与加速度连续。
  3) lockDistance / unlockDistance 构成迟滞带，防止阈值附近反复锁/放。
"""
import math

FOOT_LOCK_DIST = 0.06      # 进入锁定：趾到锚点距离 < 此值
FOOT_UNLOCK_DIST = 0.10    # 解除锁定：距离 > 此值（须 > LOCK，构成迟滞带）
FOOT_INERT_TIME = 0.10     # 惯性化时长（秒）


def cubic_inertialize(src, dst, x):
    """三次惯性化权重：x∈[0,1] -> w∈[0,1]，两端一阶导为 0。"""
    x = 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)
    return x * x * (3.0 - 2.0 * x)


class FootLock:
    """单脚锁定状态机（带迟滞）。

    状态: 'free'（跟随输入动画） / 'locked'（锁在地面锚点）
    """

    def __init__(self, lock_d=FOOT_LOCK_DIST, unlock_d=FOOT_UNLOCK_DIST,
                 inert_t=FOOT_INERT_TIME, dt=1.0 / 60.0):
        if unlock_d <= lock_d:
            raise ValueError(
                f"unlock_d({unlock_d}) 必须 > lock_d({lock_d}) —— "
                "否则无迟滞带，会在阈值附近抖动")
        self.lock_d, self.unlock_d = lock_d, unlock_d
        self.inert_t, self.dt = inert_t, dt
        self.state = 'free'
        self.anchor = None
        self._blend = 1.0        # 1.0 = 完全跟随输入，0.0 = 完全锁定

    def update(self, toe_xy, contact):
        """返回本帧实际使用的趾位置 (x, y)。"""
        x, y = float(toe_xy[0]), float(toe_xy[1])
        if self.state == 'free':
            self._blend = min(1.0, self._blend + self.dt / max(1e-9, self.inert_t))
            if contact:
                self.state = 'locked'
                self.anchor = (x, y)
                self._blend = 1.0
            return (x, y)
        d = math.hypot(x - self.anchor[0], y - self.anchor[1])
        if d > self.unlock_d:
            self.state = 'free'
            self.anchor = None
            return (x, y)
        self._blend = max(0.0, self._blend - self.dt / max(1e-9, self.inert_t))
        w = cubic_inertialize(0.0, 1.0, self._blend)
        ax, ay = self.anchor
        return (ax + (x - ax) * w, ay + (y - ay) * w)


def self_check():
    ok, bad = [], []
    def add(n, c, m=""):
        (ok if c else bad).append(n + (" " + m if m else ""))

    # 1) 迟滞：阈值附近微抖不应反复切换
    fl = FootLock(dt=1/60.)
    seq, states = [], []
    for i in range(200):
        r = 0.08 + 0.010 * math.sin(i * 0.9)      # 在 lock(0.06)/unlock(0.10) 带内抖
        xy = (r, 0.0)
        out = fl.update(xy, contact=(i == 0))
        seq.append(out); states.append(fl.state)
    flips = sum(1 for k in range(1, len(states)) if states[k] != states[k-1])
    add("1 迟滞防抖", flips == 0, f"状态跳变={flips}")

    # 2) 锁定期间位置恒定
    fl2 = FootLock(dt=1/60.)
    base = None; var = 0.0
    for i in range(120):
        out = fl2.update((0.5 + 0.001*i, 0.02), contact=(i < 3))
        if fl2.state == 'locked':
            if base is None: base = out
            var = max(var, math.hypot(out[0]-base[0], out[1]-base[1]))
    add("2 锁定期间位置恒定", var < 0.02, f"最大漂移={var:.5f}")

    # 3) 惯性化降低速度尖峰（曲率能量）
    def curv(seq):
        n=len(seq)
        if n<3: return 0.0
        acc=[]
        for k in range(1,n-1):
            ax=seq[k+1][0]-2*seq[k][0]+seq[k-1][0]
            ay=seq[k+1][1]-2*seq[k][1]+seq[k-1][1]
            acc.append(math.hypot(ax,ay))
        return sum(a*a for a in acc)/max(1,len(acc))
    raw=[]; sm=[]
    fl3=None
    prev=None
    for i in range(180):
        x = 0.02*i/60. + (0.0 if i<60 else 0.05*math.sin((i-60)*0.3))
        p=(x,0.03)
        raw.append(p)
        if i==60: fl3=FootLock(dt=1/60.)
        if fl3 is None: sm.append(p); prev=p
        else: sm.append(fl3.update(p, contact=(i==60)))
    e_raw=curv(raw); e_sm=curv(sm)
    add("3 惯性化抑制速度尖峰", e_sm <= e_raw,
        f"曲率能量 {e_raw:.2e} -> {e_sm:.2e}")

    # 4) unlock 必须大于 lock（迟滞带存在性）
    try:
        FootLock(lock_d=0.10, unlock_d=0.06); add("4 迟滞带校验", False, "未抛异常")
    except ValueError:
        add("4 迟滞带校验", True)

    print("PASS:")
    for x in ok: print("  " + x)
    if bad:
        print("FAIL:")
        for x in bad: print("  " + x)
    else:
        print("FAIL: 无")
    return not bad


if __name__ == "__main__":
    import sys
    sys.exit(0 if self_check() else 1)
