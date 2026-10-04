# 契约: proc/motion/camera
#   一句话: 相机：视高/焦距/px_per_m(Z)/反投影；人物与路必须共用同一台
#   完整契约见 motion/__init__.py
# -*- coding: utf-8 -*-
"""camera —— 共享相机（背景与人物必须是同一台）

问题：路是"从远到近"的纵深方向，而人物只有一套 2D 矢状关节
（u=前后, v=高低），没有第三个轴 w（身体侧向），于是无论路朝哪，
人物永远只能画成**侧视**、且永远**原地踏步**。

这台相机的任务不是"选个好看的视角"，而是**反解出背景画路时隐含的
那台相机**，让人物和路严格共用同一套透视。

平地面 + 针孔的三个恒等式：
    sy = v_h + f·hc / Z        地面点；hc=相机高, Z=深度
    hw = f·W  / Z              路的屏幕半宽
    ⇒  hw = (W/hc)·(sy − v_h)  ← **线性**（所以 draw_road 的 expo 必须 1.0）
    ⇒  W/hc = hw_near/(y_near − v_h)   ← 被背景唯一确定，f 消不掉它

f 反而是自由的：它只决定视野宽窄 / 绝对尺度，不影响"人对路"的比例。
"""

import math


class OrthoCam:
    """正交相机：人物表、侧视图用。s = 像素/身高单位。"""

    def __init__(self, s, cx, y0):
        self.s = float(s)
        self.cx = float(cx)
        self.y0 = float(y0)
        self.persp = False

    def px_per_m(self, Z=None):
        return self.s

    def ground_y(self, Z=None):
        return self.y0

    def depth_at(self, y):
        return None

    def proj(self, X, Z, h):
        return (self.cx + float(X) * self.s, self.y0 - float(h) * self.s, self.s)

    def road_hw(self, Z=None):
        return float("inf")


class Cam:
    """透视相机。世界：X=横向, Z=纵深(越大越远), h=离地高度(米)。"""

    def __init__(self, w, h, cx, v_h, f, hc, W):
        self.w, self.h = w, h
        self.cx, self.v_h = cx, v_h
        self.f = float(f)      # 焦距(像素)
        self.hc = float(hc)    # 相机离地高(米)
        self.W = float(W)      # 路的世界半宽(米)
        self.persp = True

    # ---- 基本换算 ----
    def px_per_m(self, Z):
        return self.f / max(float(Z), 1e-4)

    def ground_y(self, Z):
        """深度 Z 处地面在屏幕上的 y"""
        return self.v_h + self.f * self.hc / max(float(Z), 1e-4)

    def depth_at(self, y):
        """屏幕 y（地面点）对应的深度 Z"""
        dy = float(y) - self.v_h
        if dy <= 1e-6:
            return float("inf")
        return self.f * self.hc / dy

    def road_hw(self, Z):
        return self.f * self.W / max(float(Z), 1e-4)

    def proj(self, X, Z, h):
        """→ (屏幕x, 屏幕y, 该深度的 像素/米)"""
        Z = max(float(Z), 1e-4)
        s = self.f / Z
        return (self.cx + float(X) * s,
                self.v_h + (self.hc - float(h)) * s,
                s)

    def info(self):
        zn = self.depth_at(self.h - 1)
        return ("f=%.1f hc=%.2fm W=%.3fm  底边深度Z=%.2fm  底边像素/米=%.1f"
                % (self.f, self.hc, self.W, zn, self.px_per_m(zn)))


def fit(geom, cam_h=1.60, fov_h_deg=55.0, f=None):
    """从背景 geom 反解相机。

    cam_h 决定"路到底多宽"：W/hc 被背景锁死，
    所以选 cam_h=1.6m（视线高）→ 路就是一条 0.98m 宽的小径，
    这和画面观感一致（人在近处几乎占满路宽）。
    """
    w, h = geom["w"], geom["h"]
    v_h, cx = geom["horizon_y"], geom["vanish_x"]
    half_near = geom.get("road_half_near", 0.26)
    near_y = h - 1
    hw_near = w * half_near
    ratio = hw_near / max(near_y - v_h, 1.0)      # = W / cam_h
    W = ratio * cam_h
    if f is None:
        f = (w * 0.5) / math.tan(math.radians(fov_h_deg) * 0.5)
    return Cam(w, h, cx, v_h, f, cam_h, W)


# ================================================================
# 自检
# ================================================================

if __name__ == "__main__":
    from scene import kit

    ok = True

    def chk(name, cond, extra=""):
        global ok
        ok = ok and bool(cond)
        print("  %-30s %s %s" % (name, "OK" if cond else "FAIL", extra))

    print("=" * 62)
    print("  camera 自检")
    print("=" * 62)

    bg, geom = kit.compose(kit.SCENES["城墙关隘"])
    cam = fit(geom)
    print("  相机:", cam.info())

    # 1 地面往返一致
    err = max(abs(cam.depth_at(cam.ground_y(Z)) - Z) for Z in (2, 5, 10, 40))
    chk("ground_y/depth_at 往返", err < 1e-6, "最大误差 %.2e" % err)

    # 2 越远越靠近地平线，且永不越过
    ys = [cam.ground_y(Z) for Z in (2, 5, 10, 40, 200)]
    mono = all(ys[i] > ys[i + 1] for i in range(len(ys) - 1))
    chk("越远越高且单调", mono and all(y > cam.v_h for y in ys),
        "y: %s > v_h=%d" % ([int(y) for y in ys], cam.v_h))

    # 3 路与人的比例恒定（关键恒等式）
    rs = []
    for Z in (3, 6, 12, 30):
        y = cam.ground_y(Z)
        hp = cam.px_per_m(Z) * 1.70            # 1.7m 身高
        rs.append(hp / (2.0 * cam.road_hw(Z)))  # 身高 / 路全宽
    chk("身高/路宽 恒定", max(rs) - min(rs) < 1e-9,
        "%.4f~%.4f" % (min(rs), max(rs)))

    # 4 与背景画的路对得上（用 kit.road_hw 实测）
    ctx = dict(w=geom["w"], h=geom["h"], horizon_y=geom["horizon_y"],
               vanish_x=geom["vanish_x"],
               road_p=dict(half_near=geom.get("road_half_near", 0.26),
                           expo=geom.get("road_expo", 1.0)))
    dev = []
    for Z in (4, 8, 20):
        y = int(cam.ground_y(Z))
        dev.append(abs(cam.road_hw(Z) - kit.road_hw(ctx, y)))
    chk("与背景路宽一致", max(dev) < 3.0, "最大偏差 %.2f px" % max(dev))

    # 5 投影：地面点落在 ground_y
    e = 0.0
    for Z in (3, 9, 25):
        sx, sy, s = cam.proj(0.0, Z, 0.0)
        e = max(e, abs(sy - cam.ground_y(Z)))
    chk("地面点投影高度正确", e < 1e-6, "误差 %.2e" % e)

    # 6 横向偏移随深度收敛到消失点（透视收拢）
    xs = [cam.proj(1.0, Z, 0.0)[0] for Z in (3, 10, 40)]
    chk("横向随深度收拢", xs[0] > xs[1] > xs[2] > cam.cx,
        "x=%s → cx=%d" % ([round(v, 1) for v in xs], cam.cx))

    # 7 正交相机（人物表）脚底锁定
    oc = OrthoCam(s=300.0, cx=270.0, y0=880.0)
    sx, sy, s = oc.proj(0.0, 10.0, 0.0)
    sx2, sy2, _ = oc.proj(0.0, 10.0, 1.0)
    chk("正交相机 脚底/头顶", abs(sy - 880.0) < 1e-9 and abs(880.0 - sy2 - 300.0) < 1e-9,
        "脚底%.0f 身高%.0f" % (sy, sy - sy2))

    print("-" * 62)
    print("  SELF_CHECK:", "PASS" if ok else "FAIL")
