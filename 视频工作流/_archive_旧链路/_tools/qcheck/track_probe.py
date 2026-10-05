#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""track_probe —— 诊断「人物是否沿路径走 / 是否飞上天」。

为什么需要（用户要求：用工具检查，不要用人检查）：
  目测只能说"飞了"，无法定位是路径错、渲染错还是单位错。
  本工具逐帧比对【成片里人物的实际位置】vs【求解器给出的期望位置】。

业界判据：
  cgtyphoon：步幅必须与移动速度匹配，否则脚滑
  Footprints CVPR2020（项目铁律）：地平线以上不可能是可行走面

用法: python3 -m _tools.qcheck.track_probe --video 成片.mp4
"""
import argparse, json, os, sys
import numpy as np, cv2

_HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def detect_subject(f, ref_bg=None):
    """从成片帧里找人物：与背景差分找前景（同编码器，噪声低）。"""
    if ref_bg is None:
        return None
    d = cv2.absdiff(f, ref_bg).astype(np.float32).mean(axis=2)
    m = d > 25
    if m.sum() < 200:
        return None
    ys, xs = np.where(m)
    return dict(y0=int(ys.min()), y1=int(ys.max()),
                x0=int(xs.min()), x1=int(xs.max()),
                cy=float(ys.mean()), cx=float(xs.mean()), area=int(m.sum()))


def run(video, bg_path=None, spec_path=None, n=480):
    cap = cv2.VideoCapture(video)
    bg = None
    if bg_path and os.path.exists(bg_path):
        b = cv2.imread(bg_path)
        if b is not None:
            bg = cv2.resize(b, (540, 960))
    sys.path.insert(0, _HERE)
    import json as J
    spec = J.load(open(spec_path or os.path.join(_HERE, "scene_spec.json"),
                       encoding="utf-8"))
    import path as PA, build_phase_setup as BPS
    from PIL import Image
    im = np.array(Image.open(os.path.join(_HERE, "_生成", "城墙背景.png")).convert("RGB"))
    bgimg = cv2.resize(im, (540, 960))[:, :, ::-1]
    near = float(((spec.get("path") or {}).get("perspective") or {})
                 .get("near_px_per_m", 117.647))
    info = BPS.setup_path(spec, bgimg, 540, 960, near)
    pts, table = info["pts"], info["table"]
    total = float(table["total"])
    speed = float(((spec.get("biped_rig") or {}).get("gait") or {}).get("speed_m_s", 1.5))
    horizon = 482.0

    rows = []
    for i in range(n):
        ok, f = cap.read()
        if not ok:
            break
        t = i / 60.0
        # 期望：距离(米) -> 像素（注意单位！业界：必须同一量纲）
        d_m = speed * t
        d_px = (d_m * near) % total
        exp = PA.at_distance(pts, d_px, table=table)["xy"]
        got = detect_subject(f, bg)
        rows.append(dict(frame=i, t=round(t, 3),
                         exp_xy=[round(float(exp[0]), 1), round(float(exp[1]), 1)],
                         got=got))
    cap.release()
    return rows, dict(total_px=round(total, 1), speed=speed, near_px_per_m=near,
                      horizon=horizon)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--bg")
    ap.add_argument("--frames", type=int, default=480)
    ap.add_argument("--json")
    a = ap.parse_args()
    rows, meta = run(a.video, a.bg, None, a.frames)
    print(json.dumps(meta, ensure_ascii=False))

    # 判定1：期望路径是否越地平线
    above = [r for r in rows if r["exp_xy"][1] < meta["horizon"]]
    print("\n[判定1 期望路径越地平线] 帧数=%d/%d" % (len(above), len(rows)))
    if above:
        print("  前5个:", [(r["frame"], r["exp_xy"]) for r in above[:5]])

    # 判定2：期望位置的跳变（瞬移检测）
    ex = np.array([r["exp_xy"] for r in rows])
    jump = np.abs(np.diff(ex, axis=0)).sum(axis=1)
    print("\n[判定2 期望位置瞬移] 相邻帧最大位移=%.1fpx 均值=%.2fpx"
          % (jump.max(), jump.mean()))
    big = np.where(jump > 20)[0]
    print("  位移>20px 的位置数=%d" % len(big))
    if len(big):
        print("  前5个(帧号->下一帧):", [(int(b), round(float(jump[b]), 1)) for b in big[:5]])

    # 判定3：实际检测到的人物 vs 期望
    got = [r["got"] for r in rows if r["got"]]
    print("\n[判定3 实际检出] 有前景的帧=%d/%d" % (len(got), len(rows)))
    if got:
        ys = np.array([g["cy"] for g in got])
        print("  实际人物中心y: min=%.1f max=%.1f 极差=%.1f"
              % (ys.min(), ys.max(), ys.max() - ys.min()))
        print("  期望足底y   : min=%.1f max=%.1f 极差=%.1f"
              % (ex[:, 1].min(), ex[:, 1].max(), ex[:, 1].max() - ex[:, 1].min()))
        print("  -> 人物y极差若远大于期望极差，说明渲染位置与路径脱钩")
    if a.json:
        json.dump({"meta": meta, "rows": rows[:60]},
                  open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
