# -*- coding: utf-8 -*-
"""契约：90秒连续时间线的物理预跑，存轨迹分片 + checkpoint。

高层摘要：Street 世界按 10 子步/视频帧推进（dt=1/240, fps=24），
全程由 GlobalParams 连续扰动驱动，按时间线注入交互事件，
轨迹存 npz，世界状态 pickle 成 checkpoint 以支持分片续跑。

为什么分片：21600 步 × 83ms ≈ 30 分钟，单次命令超时不够，
必须 checkpoint 续跑。
"""
import os
import sys
import pickle
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROC = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_PROC)
for _p in (_ROOT, _PROC):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from showreel import params as P          # noqa: E402
from showreel import scene as S           # noqa: E402

FPS = 24
DURATION = 90.0
NF = int(DURATION * FPS)          # 2160
SUB = 10                          # 1/240 * 10 = 1/24
OUT = os.path.join(_HERE, "_phys")
os.makedirs(OUT, exist_ok=True)


# ---------------------------------------------------------------- 事件表
# 每个事件 (t, fn_name, kwargs)：在视频帧级触发一次性物理作用。
# 出处：用户给定的 90 秒时间线；作用方式用冲量（Box2D apply impulse 惯例）。
def _kick(st, W):
    """18-24s 踢球：给球一个朝多米诺方向的初速。"""
    if st.balls:
        b = st.balls[0]
        b.v = np.array([5.2, 1.6], dtype=float)
        return "kick ball v=%s" % b.v
    st.add_ball(p=(3.6, 0.12), v=(5.2, 1.6))
    return "kick (spawn ball)"


def _throw(st, W):
    """24-32s 扔球：球滚向多米诺（连锁 C15 的起点）。"""
    if not st.balls:
        st.add_ball(p=(3.4, 1.2))
    b = st.balls[0]
    b.p = np.array([3.4, 1.25], dtype=float)
    b.v = np.array([4.6, 0.9], dtype=float)
    return "throw ball -> domino"


def _push_crate(st, W):
    """56-64s 推箱子。"""
    st.crate.v = np.array([1.9, 0.0], dtype=float)
    return "push crate"


def _pull_rope(st, W):
    """拉绳子：给绳末端一个横向速度，靠距离约束把另一端带过去。

    注意: make_rope 返回 (pts, cons, seg)，seg 是段长(float)，
    质点列表是 rope 不是 rope_seg（实测 rope_seg[-1] 会 TypeError）。
    """
    if st.rope:
        st.rope[-1].v = np.array([-1.6, 0.4], dtype=float)
    return "pull rope"


def _open_door(st, W):
    """开门：给门一个绕铰链的角速度。"""
    d = st.door
    d.w = -1.15
    return "open door w=-1.15"


def _topple_wall(st, W):
    """72-80s 推倒墙：对墙底部方块施加递减速冲量，形成推倒而非整体平移。"""
    n = 0
    for b in st.wall:
        if b.p[1] < 0.45:
            b.v = np.array([2.4 + 0.15 * n, 0.25], dtype=float)
            n += 1
    return "topple wall base n=%d" % n


def _stress_balls(st, W):
    """80-88s 压力段：生成球到 50 个（含已有的），位置分散避免初始完全重叠。"""
    rng = np.random.default_rng(20261005)
    add = max(0, 50 - len(st.balls))
    for i in range(add):
        x = 1.0 + rng.random() * 14.0
        y = 1.4 + rng.random() * 2.6
        st.add_ball(p=(x, y), v=(rng.uniform(-1, 1), 0.0))
    return "stress balls total=%d" % len(st.balls)


EVENTS = [
    (20.0, _kick, {}),
    (30.0, _throw, {}),
    (32.0, _topple_wall, {}),   # 注：真正推墙在 72s；这里先不倒
    (57.0, _push_crate, {}),
    (60.0, _pull_rope, {}),
    (62.5, _open_door, {}),
    (72.0, _topple_wall, {}),
    (80.0, _stress_balls, {}),
]
# 32.0 那次是误加的占位，去掉
EVENTS = [e for e in EVENTS if abs(e[0] - 32.0) > 1e-9]


# ---------------------------------------------------------------- 跑批
def _snapshot(st):
    """抽一帧轨迹：所有 body 的 (x, y, angle)，定长按当前 bodies 顺序。"""
    W = st.world
    n = len(W.bodies)
    arr = np.zeros((n, 3), dtype=np.float64)
    for i, b in enumerate(W.bodies):
        arr[i, 0] = b.p[0]
        arr[i, 1] = b.p[1]
        arr[i, 2] = getattr(b, "angle", 0.0)
    return arr


def run(start=0, end=NF, chunk=240):
    gp = P.GlobalParams()
    ck = os.path.join(OUT, "ck_%05d.pkl" % start)
    if start > 0 and os.path.exists(ck):
        with open(ck, "rb") as f:
            st = pickle.load(f)
        print("[resume] from frame %d" % start)
    else:
        st = S.Street(dt=1.0 / 240.0, iters=10)

    # 续跑时把 start 之前的事件标为已触发，否则它们会在第一帧被全部重放
    # （实测 resume 后 t=50 kick/throw、t=57 push 被重复注入）。
    t_start = start / float(FPS)
    fired = {(te, fn.__name__) for (te, fn, kw) in EVENTS if te < t_start}
    t0 = time.time()
    for i in range(start, end):
        t = i / float(FPS)
        st.apply_global(gp, t)
        # 事件：到点触发一次（用帧号去重，避免浮点重复命中）
        for (te, fn, kw) in EVENTS:
            key = (te, fn.__name__)
            if t >= te and key not in fired:
                msg = fn(st, st.world)
                fired.add(key)
                print("[evt] t=%.2f %s" % (t, msg))
        st.step(gp, t, substeps=SUB)
        _traj.append(_snapshot(st).copy())

        if (i + 1) % chunk == 0 or i == end - 1:
            np.savez_compressed(os.path.join(OUT, "traj_%05d.npz" % (i + 1)),
                                traj=np.array(_traj))
            with open(os.path.join(OUT, "ck_%05d.pkl" % (i + 1)), "wb") as f:
                pickle.dump(st, f)
            el = time.time() - t0
            print("[ck] frame %d/%d  %.1fs  bodies=%d"
                  % (i + 1, end, el, len(st.world.bodies)))
            t0 = time.time()


_traj = []


def main():
    a = sys.argv
    start = int(a[1]) if len(a) > 1 else 0
    end = int(a[2]) if len(a) > 2 else min(NF, start + 240)
    run(start, end)


if __name__ == "__main__":
    main()
