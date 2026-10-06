# 契约: proc/showreel/camrig
#   一句话: 连续相机运镜（跟随/横移/推拉/低角度/俯拍/微距），全程 C1 连续不切镜
#   完整契约见 showreel/__init__.py
# -*- coding: utf-8 -*-
"""连续相机（90 秒不切镜）。

运镜维度与本项目相机的映射
  本项目是**单视面 2D 渲染器**：世界平面 (X 横, Z 纵深, h 高)，
  屏幕投影 sx = cx + X·f/Z ，sy = v_h + (hc − h)·f/Z
  所以可调的自由量只有四个：cx / v_h / f / hc

  运镜        | 映射                                  | 出处/说明
  ------------|---------------------------------------|------------------
  跟随 follow | cx 连续跟随目标世界 X                  | Cinematic Spline
  横移 dolly  | cx 沿样条平移                          | （近似"环绕"）
  推拉 zoom   | f 焦距连续变化（dolly zoom）            | Cinematic Spline
  低角度      | hc 相机离地高 → 小（贴地）              | 针孔投影恒等式
  俯拍        | v_h 地平线屏幕 y → 小（地面占满画面）    | 见下推导
  微距 macro  | f 大幅增大 + cx 锁定细节目标            | 同上
  手持微抖    | cx/v_h 叠加低频正弦                     | params.shake

  **俯拍方向的推导**（不是猜的）：
      ground_y(Z) = v_h + f·hc/Z ，Z→∞ 时 y→v_h（地平线）
      v_h 越小 → 地平线越高 → 地面从很上方一直铺到画面底 → 俯拍
      v_h 越大 → 地平线越低 → 画面上半全是天空 → 仰拍/低角度
  与 camera.py 文档"v_h=horizon_y"一致。

"环绕"为什么做不到（必须说清）
  真环绕需要绕 Y 轴改变方位角，而本项目渲染的是**一个固定视平面**，
  没有第三个自由度。人物的 yaw（正面/侧面/背面）是**身体属性**不是相机属性。
  → 本实现的替代方案：横移样条 + 人物 yaw 同步连续变化 + 焦距呼吸。
    观感接近"绕着走"，但严格说不是真环绕。已在缺口文档登记。

出处
[1] Cinematic Spline Tool（连续相机：spline 链、Perlin 抖动、
    dolly zoom、group framing、actor attachment）—— 上一轮已搜得
[2] Catmull-Rom 一阶连续（复用 showreel.params.spline_at）
[3] 手持抖动用低频正弦叠加而非逐帧随机（逐帧随机=抖动，需求禁止）
"""
import math

from .params import spline_at, smoothstep


class Shot:
    """一个运镜关键帧。t=秒。"""

    def __init__(self, t, cx=960.0, v_h=669.6, f=2112.0, hc=1.60,
                 follow=None, zoom=1.0):
        self.t = float(t)
        self.cx = float(cx)          # 屏幕中心 x（跟随目标时作为偏移）
        self.v_h = float(v_h)        # 地平线屏幕 y
        self.f = float(f)            # 焦距(像素)
        self.hc = float(hc)          # 相机离地高(m)
        self.follow = follow         # 跟随目标名（None=不跟随）
        self.zoom = float(zoom)      # 焦距倍率（微距/广角）


class CamRig:
    """把关键帧样条化成**每一帧**的相机参数。

    跟随目标的特殊性：
      目标世界 X 是**仿真算出来的**，不能预先样条化。
      所以跟随量单独算：cx_eff = cx_key + (−X_target·f/Z_target)·follow_w
      follow_w 本身也走样条（0→1 平滑淡入淡出），这样"开始跟随"
      和"脱离跟随"都不会硬切。
    """

    def __init__(self, shots, w=1920, h=1080, W=40.0, shake_fn=None):
        self.shots = sorted(shots, key=lambda s: s.t)
        self.w, self.h = w, h
        self.W = W
        self.shake_fn = shake_fn or (lambda t: 0.0)
        # 预展平成各维度的关键帧表
        self._k = {
            "cx": [(s.t, s.cx) for s in self.shots],
            "v_h": [(s.t, s.v_h) for s in self.shots],
            "f": [(s.t, s.f) for s in self.shots],
            "hc": [(s.t, s.hc) for s in self.shots],
            "zoom": [(s.t, s.zoom) for s in self.shots],
        }
        # follow 权重：每个 shot 有 follow 目标 → 权重 1，否则 0，样条平滑
        self._fw = [(s.t, 1.0 if s.follow else 0.0) for s in self.shots]
        self._follow_name = [(s.t, s.follow) for s in self.shots]

    def _follow_name_at(self, t):
        """取当前该跟随谁（取最近的前一个 shot）。"""
        name = None
        for tk, nm in self._follow_name:
            if tk <= t:
                name = nm
        return name

    def cam(self, t, targets=None, base_cx=None):
        """→ motion.camera.Cam。targets: {name: (X, Z)} 世界坐标。"""
        from motion import camera as C
        cx = spline_at(self._k["cx"], t)
        v_h = spline_at(self._k["v_h"], t)
        f = spline_at(self._k["f"], t) * spline_at(self._k["zoom"], t)
        hc = spline_at(self._k["hc"], t)
        fw = spline_at(self._fw, t)

        # ---- 跟随：把目标顶到画面中心 ----
        if targets and fw > 1e-6:
            nm = self._follow_name_at(t)
            if nm and nm in targets:
                X, Z = targets[nm]
                s = f / max(Z, 1e-4)
                # 目标应出现在 (base_cx) 处 → cx = base_cx − X·s
                cx_goal = (base_cx if base_cx is not None else self.w * 0.5) - X * s
                cx = cx + (cx_goal - cx) * fw

        # ---- 手持微抖（低频正弦，非逐帧随机）----
        sh = self.shake_fn(t)
        cx += sh * 26.0
        v_h += sh * 14.0

        return C.Cam(self.w, self.h, cx, v_h, f, hc, self.W)


def default_shots():
    """90 秒默认运镜表（对应需求各段）。"""
    W, H = 1920, 1080
    return [
        # 0-5s  低角度广角建立：贴地(0.55m)、广角(f 小)、地平线偏低
        Shot(0.0, cx=960, v_h=H * 0.62, f=1250, hc=0.55, follow=None, zoom=1.0),
        Shot(5.0, cx=960, v_h=H * 0.62, f=1250, hc=0.55, follow=None, zoom=1.0),
        # 5-12s 跟随女性（跑动）
        Shot(6.0, cx=960, v_h=H * 0.60, f=1500, hc=0.90, follow="woman", zoom=1.0),
        Shot(12.0, cx=960, v_h=H * 0.60, f=1650, hc=1.10, follow="woman", zoom=1.0),
        # 12-18s 跟随 + 略推
        Shot(15.0, cx=960, v_h=H * 0.58, f=1900, hc=1.30, follow="woman", zoom=1.0),
        # 18-24s 微距：看手（挥手/捡杯）
        Shot(19.0, cx=960, v_h=H * 0.55, f=3400, hc=1.40, follow="woman", zoom=1.0),
        Shot(24.0, cx=960, v_h=H * 0.62, f=1800, hc=1.35, follow="woman", zoom=1.0),
        # 24-32s 横移跟球
        Shot(28.0, cx=960, v_h=H * 0.63, f=1600, hc=1.30, follow="ball0", zoom=1.0),
        # 32-40s 俯拍看多米诺链
        Shot(34.0, cx=960, v_h=H * 0.28, f=1500, hc=3.20, follow=None, zoom=1.0),
        Shot(40.0, cx=960, v_h=H * 0.30, f=1550, hc=3.00, follow=None, zoom=1.0),
        # 40-48s 跟随球飞向男人
        Shot(44.0, cx=960, v_h=H * 0.60, f=1750, hc=1.40, follow="ball0", zoom=1.0),
        # 48-56s 拉远看三人
        Shot(50.0, cx=960, v_h=H * 0.58, f=1250, hc=1.50, follow=None, zoom=1.0),
        Shot(56.0, cx=960, v_h=H * 0.58, f=1300, hc=1.50, follow="woman", zoom=1.0),
        # 56-64s 跟随开门
        Shot(60.0, cx=960, v_h=H * 0.56, f=1700, hc=1.35, follow="woman", zoom=1.0),
        # 64-72s 慢动作微距（timeScale 0.3）
        Shot(66.0, cx=960, v_h=H * 0.52, f=3000, hc=1.30, follow="woman", zoom=1.0),
        Shot(72.0, cx=960, v_h=H * 0.62, f=1600, hc=1.35, follow="woman", zoom=1.0),
        # 72-80s 拉远看墙倒
        Shot(76.0, cx=960, v_h=H * 0.50, f=1300, hc=1.80, follow=None, zoom=1.0),
        # 80-88s 压力段：俯拍全景
        Shot(82.0, cx=960, v_h=H * 0.32, f=1150, hc=3.60, follow=None, zoom=1.0),
        Shot(88.0, cx=960, v_h=H * 0.45, f=1400, hc=2.20, follow=None, zoom=1.0),
        # 88-90s 收尾：微距看脸（回头微笑）
        Shot(89.0, cx=960, v_h=H * 0.56, f=3600, hc=1.45, follow="woman", zoom=1.0),
        Shot(90.0, cx=960, v_h=H * 0.56, f=3600, hc=1.45, follow="woman", zoom=1.0),
    ]


def self_check():
    ok = []

    def chk(name, cond, extra=""):
        ok.append((name, bool(cond), extra))

    rig = CamRig(default_shots(), shake_fn=lambda t: 0.0)

    # 1) 连续性：焦距/机位逐帧变化必须有界（无切镜）
    dt = 1.0 / 24.0
    prev = None
    mx_f = mx_c = 0.0
    t = 0.0
    while t <= 90.0:
        c = rig.cam(t, targets=None)
        if prev is not None:
            mx_f = max(mx_f, abs(c.f - prev[0]))
            mx_c = max(mx_c, abs(c.cx - prev[1]))
            mx_c = max(mx_c, abs(c.v_h - prev[2]) * 1.0)
        prev = (c.f, c.cx, c.v_h)
        t += dt
    chk("焦距无跳变", mx_f < 260.0, "max_df=%.1f px/frame" % mx_f)
    chk("机位无跳变", mx_c < 90.0, "max_d=%.1f px/frame" % mx_c)

    # 2) 关键帧命中
    c0 = rig.cam(0.0, targets=None)
    chk("t=0 贴地广角", abs(c0.hc - 0.55) < 1e-6, "hc=%.2f" % c0.hc)
    c34 = rig.cam(34.0, targets=None)
    chk("t=34 俯拍(地平线高)", c34.v_h < 1080 * 0.35, "v_h=%.0f" % c34.v_h)

    # 3) 微距段焦距显著大于广角段
    f19 = rig.cam(19.0, targets=None).f
    f0 = rig.cam(0.0, targets=None).f
    chk("微距>广角", f19 > f0 * 1.8, "f19=%.0f f0=%.0f" % (f19, f0))

    # 4) 跟随确实生效：目标横向移动时 cx 反向补偿
    a = rig.cam(8.0, targets={"woman": (0.0, 6.0)})
    b = rig.cam(8.0, targets={"woman": (3.0, 6.0)})
    chk("跟随随目标移动", abs(a.cx - b.cx) > 50.0, "d_cx=%.1f" % abs(a.cx - b.cx))

    # 5) 相机高恒正（不会翻转）
    hs = [rig.cam(t / 4.0, targets=None).hc for t in range(0, 360)]
    chk("相机高恒正", all(x > 0.05 for x in hs), "min=%.3f" % min(hs))

    n_pass = sum(1 for _, c, _ in ok if c)
    for name, c, extra in ok:
        print("  %s %s %s" % ("OK " if c else "NG ", name, extra))
    print("camrig self_check: %d/%d" % (n_pass, len(ok)))
    return n_pass == len(ok)


if __name__ == "__main__":
    import os as _os, sys as _sys
    _d = _os.path.dirname(_os.path.abspath(__file__))
    for _i in range(4):
        _d = _os.path.dirname(_d)
        if _os.path.basename(_d) == "_proc":
            break
    for _p in (_os.path.dirname(_d), _d):
        if _p not in _sys.path:
            _sys.path.insert(0, _p)
    sys.exit(0 if self_check() else 1)
