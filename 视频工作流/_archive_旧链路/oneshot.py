#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""X_i：一次性动作（转身 / 停下 / 挥手 / 交互起手）的表示与播放。

业界两条路线（本模块取第一条，第二条留给后续）：
  A. Montage + Slot + AnimNotify（UE / Unity 通行做法）
     - Montage：打断当前状态机、播一段、播完回原状态（攻击/翻滚/被击退）
     - Slot：把 Montage 的姿态插入 AnimGraph，不打断底层 locomotion
     - AnimNotify：动画帧上的信号点（落脚发声、挥刀到一半开伤害判定）
     - 中断必须可释放：不能因为一方的完成回调没到就把另一方冻住
  B. Motion Matching（育碧方案，黑神话采用）
     - 按"当前姿态 + 预测轨迹"的 cost 从动画库检索下一帧
     - cost = 当前项（骨骼匹配/速度/脚步位置）+ 未来项（未来位置/朝向/速度）
     - 免手工连线状态机；代价是数据量与检索开销

本模块只做【结构与时序】，不绑定具体引擎。
"""
from typing import Callable

MONTAGE_DEFAULT_SLOT = "DefaultSlot"


class Notify:
    """AnimNotify：动画时间轴上的一个信号点。"""

    __slots__ = ("t", "name", "payload", "fired")

    def __init__(self, t: float, name: str, payload=None):
        if t < 0:
            raise ValueError("Notify.t 须 >= 0")
        self.t = float(t)
        self.name = str(name)
        self.payload = payload
        self.fired = False

    def reset(self):
        self.fired = False

    def __repr__(self):
        return f"Notify(t={self.t:.3f}, {self.name})"


class Montage:
    """一次性动作段：有明确起止，播完回到原状态。

    duration 必须 > 0；notifies 按时间升序（构造时自动排序）。
    """

    def __init__(self, name: str, duration: float,
                 slot: str = MONTAGE_DEFAULT_SLOT,
                 notifies=None, blend_in: float = 0.1,
                 blend_out: float = 0.1):
        if duration <= 0:
            raise ValueError("Montage.duration 须 > 0")
        if blend_in < 0 or blend_out < 0:
            raise ValueError("blend 时间须 >= 0")
        self.name = name
        self.duration = float(duration)
        self.slot = slot
        self.blend_in = float(blend_in)
        self.blend_out = float(blend_out)
        self.notifies = sorted(notifies or [], key=lambda n: n.t)
        self._t = 0.0
        self._playing = False
        self._interrupted = False
        for n in self.notifies:
            if n.t > self.duration:
                raise ValueError(
                    f"Notify '{n.name}' t={n.t} 超出 duration={self.duration}")

    # ---- 播放控制 ----
    def play(self):
        self._t = 0.0
        self._playing = True
        self._interrupted = False
        for n in self.notifies:
            n.reset()
        return self

    def stop(self):
        """中断。必须可调用 —— 业界明确要求：
        不能因对方回调未到就把角色冻住。"""
        if self._playing:
            self._interrupted = True
        self._playing = False
        return self

    def tick(self, dt: float, on_notify: Callable = None):
        """推进 dt 秒，触发到达的 Notify。返回本帧触发的 Notify 列表。"""
        if not self._playing or dt < 0:
            return []
        prev = self._t
        self._t = min(self._t + dt, self.duration)
        fired = []
        for n in self.notifies:
            if not n.fired and prev < n.t <= self._t:
                n.fired = True
                fired.append(n)
                if on_notify:
                    on_notify(n)
        if self._t >= self.duration:
            self._playing = False
        return fired

    # ---- 查询 ----
    @property
    def t(self):
        return self._t

    @property
    def playing(self):
        return self._playing

    @property
    def completed(self):
        """是否正常播完（被中断则为 False）。"""
        return (not self._playing) and (not self._interrupted) \
            and self._t >= self.duration

    @property
    def interrupted(self):
        return self._interrupted

    @property
    def progress(self):
        return 0.0 if self.duration <= 0 else self._t / self.duration

    def weight(self):
        """当前混入权重（blend in / out 包络），用于 Slot 混合。"""
        if not self._playing and self._t <= 0:
            return 0.0
        w = 1.0
        if self.blend_in > 0 and self._t < self.blend_in:
            w = min(w, self._t / self.blend_in)
        rem = self.duration - self._t
        if self.blend_out > 0 and rem < self.blend_out:
            w = min(w, rem / self.blend_out)
        return max(0.0, min(1.0, w))


class MontageTrack:
    """一个 Slot 上的 Montage 播放轨（同时只播一个）。"""

    def __init__(self, slot: str = MONTAGE_DEFAULT_SLOT):
        self.slot = slot
        self.current = None

    def play(self, montage: Montage):
        if self.current is not None and self.current.playing:
            self.current.stop()     # 打断旧的，避免两个同时占 Slot
        self.current = montage.play()
        return self.current

    def tick(self, dt, on_notify=None):
        if self.current is None:
            return []
        return self.current.tick(dt, on_notify)

    def release(self):
        """释放锁：把当前 Montage 停掉，交还状态机控制权。"""
        if self.current is not None:
            self.current.stop()
            self.current = None


def self_check():
    ok, bad = [], []

    def add(n, c, m=""):
        (ok if c else bad).append(n + (" " + m if m else ""))

    # 1 基本播放与完成
    m = Montage("转身", 0.5, notifies=[Notify(0.25, "foot_plant")])
    m.play()
    fired = []
    for _ in range(10):
        fired += m.tick(0.1)
    add("1 播完 completed", m.completed, "t=%.2f" % m.t)
    add("2 Notify 触发一次", len(fired) == 1, "fired=%d" % len(fired))

    # 2 中断必须释放（业界铁律）
    m2 = Montage("挥手", 1.0)
    m2.play()
    m2.tick(0.3)
    m2.stop()
    add("3 中断后 completed=False", not m2.completed)
    add("4 中断后 interrupted=True", m2.interrupted)
    m2.tick(1.0)
    add("5 中断后不再推进", abs(m2.t - 0.3) < 1e-9, "t=%.2f" % m2.t)

    # 3 Slot 打断旧的
    tr = MontageTrack()
    a = Montage("A", 1.0)
    b = Montage("B", 1.0)
    tr.play(a)
    tr.play(b)
    add("6 Slot 只保留最新", tr.current is b)
    add("7 旧的被标记中断", a.interrupted)

    # 4 release 释放锁
    tr.release()
    add("8 release 后无占用", tr.current is None)

    # 5 参数校验
    try:
        Montage("x", 0)
        add("9 duration<=0 报错", False)
    except ValueError:
        add("9 duration<=0 报错", True)
    try:
        Montage("x", 1.0, notifies=[Notify(2.0, "late")])
        add("10 Notify 越界报错", False)
    except ValueError:
        add("10 Notify 越界报错", True)

    # 6 blend 包络
    m3 = Montage("m", 1.0, blend_in=0.2, blend_out=0.2)
    m3.play()
    m3.tick(0.1)
    w_in = m3.weight()
    m3.tick(0.8)
    w_out = m3.weight()
    add("11 blend_in 包络", 0.0 < w_in < 1.0, "w=%.2f" % w_in)
    add("12 blend_out 包络", 0.0 < w_out < 1.0, "w=%.2f" % w_out)

    print("PASS:")
    for x in ok:
        print("  " + x)
    if bad:
        print("FAIL:")
        for x in bad:
            print("  " + x)
    else:
        print("FAIL: 无")
    return not bad


if __name__ == "__main__":
    import sys
    sys.exit(0 if self_check() else 1)
