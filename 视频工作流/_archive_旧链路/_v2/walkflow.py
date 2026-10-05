# -*- coding: utf-8 -*-
"""walkflow —— 走路循环 + 沿路径推进（在 matteflow 之上加位移）。

架构（与 matteflow 一致，只多一层推进）：
  背景 1 张，全程不动          → 背景像素级一致，不靠生图
  人物绿幕 N 格 → 抠 alpha     → 运动区精确已知
  走路循环按时间取相位          → 步态
  沿路径按【世界米】推进        → 位移 + 透视缩放

为什么推进必须用世界米而不是像素（V2 的病，实测过的）：
  路径 6 段，世界长度每段都 8.10m（等距），但像素长度
    段0 238.2px  段1 98.4px  段2 53.8px  段3 33.8px  段4 23.3px  段5 17.0px
  同样走 8.1 米，近端跨 238px、远端只需 17px。
  按像素匀速推进 → 实测世界速度 1.5 → 4.14 → 9.41 → 54.76 m/s（失控）。
  根因：横向 px_per_m=(y-v_h)/h 与深度 px_per_m=(y-v_h)^2/(f*h) 是两个量，
  比值从 3.39 一路涨到 17.82，不是常数。
"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import _ground_arc as GA   # noqa: E402
import matteflow as MF     # noqa: E402
import interp as IT        # noqa: E402


# ---------- 路径：用世界坐标定义，不用屏幕控制点 ----------
def make_cam(v_h: float = 482.0, v_x: float = 270.0,
             h: float = 3.366, f: float = 1344.0) -> dict:
    """成片 540×960。v_x 取画面中心 270（原 spec 是 474，那是 960 宽的画面）。

    为什么改 v_x：原路径 x∈[60,395] 是按 960 宽画面给的，
    竖屏 540 宽下整条路径会跑到画面外。改消失点到画面中心后，
    路径从画面下方一路收敛到中心，构图才对。
    """
    return {"v_h": v_h, "v_x": v_x, "h": h, "f": f,
            "v_y": v_h}


def walk_line(X0: float, Z0: float, Z1: float, n: int = 40) -> list:
    """一条世界空间直线（X 恒定），采样成屏幕控制点。"""
    pts = []
    for i in range(n):
        Z = Z0 + (Z1 - Z0) * i / (n - 1)
        pts.append(GA.forward_project(X0, Z, make_cam()))
    return pts


def pick_X0(x_near: float, Z0: float, cam: dict) -> float:
    """给定近端希望的屏幕 x，反解世界横向 X（保证路径在画面内）。"""
    return (x_near - cam["v_x"]) * Z0 / cam["f"]


# ---------- 主流程 ----------
def run(bg_path: str, sheet_path: str, cols: int = 3, rows: int = 2,
        speed: float = 0.60, cycle_s: float = 1.667,
        height_m: float = 1.70, height_ratio: float = 0.34,
        total_s: float = 12.0, fps: int = 60,
        x_near: float = 150.0, Z0: float = 11.4, Z1: float = 60.0,
        out_size=(540, 960), out_path: str = None,
        bg_shift: bool = False) -> dict:
    """出片：人物沿路径走远。

    bg_shift=True 时背景横向平移做相机跟随（人物保持在画面中部）；
    False 时背景不动，人物自己走远变小（透视走远的观感更强）。
    """
    bg0 = cv2.imread(bg_path, cv2.IMREAD_COLOR)
    if bg0 is None:
        raise SystemExit(f"读背景失败: {bg_path}")
    bg0 = cv2.resize(bg0, tuple(out_size), interpolation=cv2.INTER_AREA)
    H, W = bg0.shape[:2]

    cam = make_cam(v_x=W / 2.0, v_h=H / 2.0)
    X0 = pick_X0(x_near, Z0, cam)
    pts = walk_line(X0, Z0, Z1, n=40)
    wtable = GA.world_arc_table(pts, cam)

    # 走路循环：N 格 → 插帧 → 一个周期的完整序列（BGRA）
    cells = MF.cut_sheet(sheet_path, cols, rows)
    bgras = MF.trim_all(MF.key_all(cells))
    nk = len(bgras)
    mul = max(1, round(cycle_s * fps / nk) - 1)
    # 关键帧先贴到透明底上插帧，避免把背景插进去
    ph = bgras[0].shape[0]
    keys = [b for b in bgras]
    loop = IT.close_loop(keys, mul, lock_bg=False)
    # close_loop 可能丢 alpha，这里确保 4 通道
    loop = [f if f.ndim == 3 and f.shape[2] == 4
            else cv2.cvtColor(f, cv2.COLOR_BGR2BGRA) for f in loop]
    # 首帧 alpha 兜底
    for f in loop:
        if f[..., 3].max() == 0:
            f[..., 3] = 255
    nloop = len(loop)

    # 素材隐含 px/m：trim 后人物高 ph 像素，代表 height_m 米
    src_px_per_m = ph / height_m

    nframe = int(round(total_s * fps))
    frames = []
    trace = []
    for i in range(nframe):
        t = i / fps
        d_m = speed * t
        if d_m >= wtable["total"]:
            break
        r = GA.at_world_distance(d_m, wtable, cam)
        x, y = float(r["xy"][0]), float(r["xy"][1])
        if y <= cam["v_h"] + 2:
            break
        ppm = GA.px_per_m_lateral(y, cam)
        scale = (height_m * ppm) / ph
        gi = int((t % cycle_s) / cycle_s * nloop) % nloop
        bgra = loop[gi]
        bg = bg0
        if bg_shift:
            dx = int(round(x_near - x))
            bg = np.roll(bg0, dx, axis=1)
        frames.append(MF.place(bg, bgra, x, y, scale))
        if i % max(1, nframe // 12) == 0:
            trace.append((round(t, 2), round(x, 1), round(y, 1),
                          round(scale, 3), round(ppm, 1)))

    if out_path:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        vw = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"),
                             fps, (W, H))
        for f in frames:
            vw.write(f.astype(np.uint8))
        vw.release()

    return {"frames": len(frames), "dur_s": len(frames) / fps,
            "X0_m": X0, "path_total_m": wtable["total"],
            "cycle_frames": nloop, "src_px_per_m": src_px_per_m,
            "trace": trace, "out": out_path}


# ---------- 自检 ----------
def self_check() -> None:
    cam = make_cam()
    # 1) 世界直线：X 恒定，Z 单调
    X0 = pick_X0(150.0, 11.4, cam)
    line = walk_line(X0, 11.4, 60.0, n=40)
    XZ = [GA.back_project(p[0], p[1], cam) for p in line]
    Xs = [round(x, 3) for x, _ in XZ]
    Zs = [z for _, z in XZ]
    assert max(Xs) - min(Xs) < 0.01, f"不是世界直线: {Xs[:3]}"
    assert all(Zs[i] < Zs[i + 1] for i in range(len(Zs) - 1)), "Z 非单调"

    # 2) 屏幕 y 单调下降（越走越远 = 越靠近地平线）
    ys = [p[1] for p in line]
    assert all(ys[i] > ys[i + 1] for i in range(len(ys) - 1)), "y 非单调"

    # 3) 透视缩放：近端/远端 比值
    ppm0 = GA.px_per_m_lateral(ys[0], cam)
    ppm1 = GA.px_per_m_lateral(ys[-1], cam)
    assert ppm0 / ppm1 > 3.0, f"透视收窄不足: {ppm0/ppm1:.2f}"

    # 4) 世界速度恒定：等时间间隔的世界位移必须等差
    wt = GA.world_arc_table(line, cam)
    ds = [GA.at_world_distance(speed * t, wt, cam)["d"]
          for speed, t in ((0.6, 1.0), (0.6, 2.0), (0.6, 3.0))]
    assert abs((ds[1] - ds[0]) - (ds[2] - ds[1])) < 0.05, ds

    # 5) 真实素材跑通并出片
    sheet = os.path.join(ROOT, "_生成", "玄奘_走6格.png")
    bgp = os.path.join(ROOT, "_生成", "城墙背景.png")
    if os.path.exists(sheet) and os.path.exists(bgp):
        r = run(bgp, sheet, cols=3, rows=2, speed=0.60,
                cycle_s=1.667, total_s=6.0,
                out_path=os.path.join(HERE, "out", "_walk_t.mp4"))
        assert r["frames"] > 30, r["frames"]
        # 走远：末帧 y 必须明显小于首帧
        assert r["trace"][-1][2] < r["trace"][0][2] - 20, r["trace"]
        # 缩小：末帧 scale 必须小于首帧
        assert r["trace"][-1][3] < r["trace"][0][3] * 0.95, r["trace"]
        os.remove(r["out"])
        tr = r["trace"]
    else:
        tr = []

    print("walkflow self_check OK  世界直线X=%.3f 透视收窄%.2fx | trace=%s"
          % (X0, ppm0 / ppm1, tr[:3]))


if __name__ == "__main__":
    self_check()
