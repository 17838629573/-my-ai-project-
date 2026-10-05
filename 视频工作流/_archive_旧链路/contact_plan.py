#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""X_g / X_e / X_f 双人与多人接触约束。

业界（InterControl）把交互建成 Contact Plan：
  contact_list     : 关节对，距离应 ≈ 0（接触）
  separation_list  : 关节对，距离须 > contact_threshold（防穿模）
  contact_bound    : [ts, te] 接触发生的帧区间
  contact_threshold: separation 的最小分离距离

核心洞察（论文）：
  交互可以简化为几何问题 —— 哪些关节该靠近（contact），哪些该远离（avoidance）。
  握手只需 contact_list；打斗【必须同时】加 separation_list，否则会互相穿模。

X_g 时间轴同步（双角色精灵规范）：
  独立生成两个角色的动作【不保证】手/武器/接触时间匹配。
  必须先约定：地面锚点、相对位置、朝向、接触点、接触时间，
  双方共享同一事件时间轴。中断时要释放临时移动锁，
  否则一方会因等不到对方完成回调而冻结。
"""
import math

# SMPL 风格关节名（业界交互计划用的命名约定）
JOINTS = ("head", "neck", "spine", "spine1", "spine2",
          "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
          "left_wrist", "right_wrist", "left_hand", "right_hand",
          "left_knee", "right_knee", "left_ankle", "right_ankle",
          "left_foot", "right_foot")

CONTACT_TOL = 1e-4          # 接触判定容差（米）
DEFAULT_THRESHOLD = 0.15    # separation 默认最小间距（米）


class ContactPlan:
    """交互计划：谁在什么时候、和谁、以什么方式接触。"""

    def __init__(self, contact_list=None, separation_list=None,
                 contact_bound=None, contact_threshold=DEFAULT_THRESHOLD,
                 text_list=None):
        self.contact_list = [tuple(p) for p in (contact_list or [])]
        self.separation_list = [tuple(p) for p in (separation_list or [])]
        self.contact_bound = tuple(contact_bound) if contact_bound else None
        self.contact_threshold = float(contact_threshold)
        self.text_list = list(text_list or [])
        self._validate()

    def _validate(self):
        for p in self.contact_list + self.separation_list:
            if len(p) != 2:
                raise ValueError(f"关节对须为 2 元组，得到 {p}")
        if self.contact_bound is not None:
            ts, te = self.contact_bound
            if te < ts:
                raise ValueError(f"contact_bound 起止颠倒: {self.contact_bound}")
        if self.contact_threshold <= 0:
            raise ValueError("contact_threshold 须 > 0")
        # 同一对关节不能既要求接触又要求分离
        both = set(self.contact_list) & set(self.separation_list)
        if both:
            raise ValueError(f"关节对同时出现在 contact 与 separation: {both}")

    def active(self, frame):
        """该帧是否处于接触约束生效区间。"""
        if self.contact_bound is None:
            return True
        ts, te = self.contact_bound
        return ts <= frame <= te

    def contact_loss(self, poses_a, poses_b, frame=None):
        """接触约束损失：各 contact 对的平方距离和。
        poses_* : {关节名: (x,y,z)}"""
        if frame is not None and not self.active(frame):
            return 0.0
        s = 0.0
        for ja, jb in self.contact_list:
            pa, pb = poses_a.get(ja), poses_b.get(jb)
            if pa is None or pb is None:
                raise KeyError(f"缺关节: {ja} / {jb}")
            s += sum((pa[k] - pb[k]) ** 2 for k in range(3))
        return s

    def separation_loss(self, poses_a, poses_b, frame=None):
        """分离损失：距离小于阈值时的缺口平方和（防穿模）。"""
        if frame is not None and not self.active(frame):
            return 0.0
        s = 0.0
        for ja, jb in self.separation_list:
            pa, pb = poses_a.get(ja), poses_b.get(jb)
            if pa is None or pb is None:
                raise KeyError(f"缺关节: {ja} / {jb}")
            d = math.sqrt(sum((pa[k] - pb[k]) ** 2 for k in range(3)))
            if d < self.contact_threshold:
                s += (self.contact_threshold - d) ** 2
        return s

    def total_loss(self, poses_a, poses_b, frame=None, w_sep=1.0):
        return (self.contact_loss(poses_a, poses_b, frame)
                + w_sep * self.separation_loss(poses_a, poses_b, frame))

    def min_pair_distance(self, poses_a, poses_b):
        """当前最小的 separation 对间距（检测是否穿模）。"""
        if not self.separation_list:
            return float("inf")
        best = float("inf")
        for ja, jb in self.separation_list:
            pa, pb = poses_a[ja], poses_b[jb]
            best = min(best, math.sqrt(sum((pa[k] - pb[k]) ** 2 for k in range(3))))
        return best


def solve_contact(plan, poses_a, poses_b, frame=None,
                  iters=40, lr=0.5, joints_a=None, joints_b=None):
    """梯度下降求解：把 A 的接触关节推向 B 的目标关节。

    业界用 L-BFGS 在扩散采样中强制约束；这里用简化的梯度下降，
    纯 numpy 无依赖，够做确定性验证。
    """
    ja_list = joints_a or sorted({p[0] for p in plan.contact_list} |
                                 {p[0] for p in plan.separation_list})
    A = {j: list(poses_a[j]) for j in ja_list}
    tgt = {p[0]: poses_b[p[1]] for p in plan.contact_list}
    sep_tgt = {p[0]: poses_b[p[1]] for p in plan.separation_list}

    hist = []
    for it in range(iters):
        g = {j: [0.0, 0.0, 0.0] for j in ja_list}
        for j in ja_list:
            if j in tgt:
                t = tgt[j]
                for k in range(3):
                    g[j][k] += 2.0 * (A[j][k] - t[k])
            if j in sep_tgt:
                t = sep_tgt[j]
                d = math.sqrt(sum((A[j][k] - t[k]) ** 2 for k in range(3))) or 1e-9
                if d < plan.contact_threshold:
                    for k in range(3):
                        g[j][k] -= 2.0 * (plan.contact_threshold - d) * (A[j][k] - t[k]) / d
        loss = plan.total_loss({**poses_a, **{j: tuple(A[j]) for j in ja_list}},
                               poses_b, frame)
        hist.append(loss)
        if loss < 1e-12:
            break
        for j in ja_list:
            for k in range(3):
                A[j][k] -= lr * g[j][k]
    out = dict(poses_a)
    for j in ja_list:
        out[j] = tuple(A[j])
    return out, hist


# ---------- X_g 时间轴同步 ----------
class InteractionTimeline:
    """共享事件时间轴 —— 双人动作必须先约定再生成。"""

    def __init__(self, fps=30.0):
        self.fps = float(fps)
        self.events = []      # [(name, ts, te)]
        self.locks = {}       # actor -> 是否持有移动锁

    def add_event(self, name, ts, te):
        if te < ts:
            raise ValueError(f"事件区间颠倒: {name} {ts}-{te}")
        self.events.append((name, float(ts), float(te)))
        self.events.sort(key=lambda e: e[1])

    def events_at(self, t):
        return [n for (n, ts, te) in self.events if ts <= t <= te]

    def acquire(self, actor):
        self.locks[actor] = True

    def release(self, actor):
        """中断时必须释放，否则一方会冻结等不到对方回调。"""
        self.locks.pop(actor, None)

    def release_all(self):
        self.locks.clear()

    def contact_window(self, name):
        for (n, ts, te) in self.events:
            if n == name:
                return (int(round(ts * self.fps)), int(round(te * self.fps)))
        return None


def self_check():
    ok, bad = [], []
    def add(n, c, m=""):
        (ok if c else bad).append(n + (" " + m if m else ""))

    # X_e 握手：只需 contact_list
    A = {"right_hand": (0.0, 1.0, 0.0), "right_wrist": (-0.05, 1.0, 0.0)}
    B = {"right_hand": (0.40, 1.05, 0.0), "left_hand": (0.9, 1.0, 0.0)}
    plan = ContactPlan(contact_list=[("right_hand", "right_hand")],
                       contact_bound=[0.0, 1.0])
    A2, hist = solve_contact(plan, A, B)
    d = math.dist(A2["right_hand"], B["right_hand"])
    add("1 握手接触收敛", d < 1e-3, f"末端距离={d:.2e} 迭代={len(hist)}")
    add("2 握手无需separation", plan.separation_loss(A2, B) == 0.0)

    # X_f 打斗：contact + separation 同时
    plan2 = ContactPlan(contact_list=[("right_hand", "spine")],
                        separation_list=[("right_hand", "head")],
                        contact_threshold=0.25, contact_bound=[0.0, 1.0])
    A3 = {"right_hand": (0.0, 1.0, 0.0)}
    B3 = {"spine": (0.5, 1.0, 0.0), "head": (0.5, 1.5, 0.0)}
    before = math.dist(A3["right_hand"], B3["head"])
    A4, h2 = solve_contact(plan2, A3, B3)
    after = math.dist(A4["right_hand"], B3["head"])
    add("3 打斗接触成立", math.dist(A4["right_hand"], B3["spine"]) < 1e-3,
        f"d={math.dist(A4['right_hand'], B3['spine']):.2e}")
    add("4 separation防穿模", after >= plan2.contact_threshold - 1e-6,
        f"头部间距 {before:.3f} -> {after:.3f} (阈值{plan2.contact_threshold})")

    # 冲突校验：同一对不能既接触又分离
    try:
        ContactPlan(contact_list=[("a", "b")], separation_list=[("a", "b")])
        add("5 冲突校验", False, "未抛异常")
    except ValueError:
        add("5 冲突校验", True)

    # contact_bound 生效区间
    add("6 区间内生效", plan.active(0.5))
    plan3 = ContactPlan(contact_list=[("a", "b")], contact_bound=[2.0, 3.0])
    add("7 区间外不生效", not plan3.active(1.0))

    # X_g 时间轴
    tl = InteractionTimeline(fps=30.0)
    tl.add_event("handshake", 1.0, 1.5)
    add("8 接触窗口换算", tl.contact_window("handshake") == (30, 45),
        str(tl.contact_window("handshake")))
    tl.acquire("A"); tl.acquire("B")
    add("9 持有锁", tl.locks == {"A": True, "B": True})
    tl.release_all()
    add("10 中断后释放锁", tl.locks == {}, str(tl.locks))

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
