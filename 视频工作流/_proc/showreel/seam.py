"""showreel/seam.py — 分段渲染的「接缝一致性」检测（流式，不全帧入内存）。

契约: proc/showreel/seam
   一句话: 段内跳帧与段间接缝的流式检测，不全帧入内存

输入: _seg/seg_*.mp4（分段渲染产物）
输出: 每段的段内跳帧统计 + 相邻段接缝处（前段末帧 vs 后段首帧）的跳变量

为什么必须流式（实测，非推测）:
  第一版把 25 段 × 60 帧 × 1080p 全部读进内存 = 12 GB，
  而本机可用内存 2 GB —— 进程直接被 OOM kill，无任何输出（连报错都没有）。
  改为「逐帧读、只保留首帧/末帧/前一帧」，峰值内存 < 20 MB。

为什么需要单独做这个:
  jumpscan.scan() 只吃单文件，只能看段内；而分段渲染最大的风险在**接缝**——
  每段是独立子进程，若任何状态（相机样条、雨滴 rng、物理查表索引、时间 t）
  在段边界被重新初始化，接缝处就会出现段内不存在的硬跳。
  判据: seam_ratio = 接缝差 / 段内相邻帧差中位数，>3.0 判 FAIL
       （与项目既有 frame_jump_ratio < 3.0 阈值一致）。

用法: python3 showreel/seam.py [--dir _seg] [--w 320]
  下采样到小尺寸再比，既省内存又抑制编码噪声（实测 320 宽足够定位硬跳）。
依赖: cv2 numpy
来源: 判据阈值沿用 tests/harness.py 的 frame_jump_ratio < 3.0。
"""
import os
import sys
import numpy as np
import cv2

W = 320


def scan_file(path, w=W):
    """流式扫单文件: 返回 (首帧, 末帧, 段内差数组)。"""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return None
    first = None
    last = None
    prev = None
    diffs = []
    n = 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY).astype(np.float32)
        if w and g.shape[1] > w:
            sc = w / float(g.shape[1])
            g = cv2.resize(g, (w, int(g.shape[0] * sc)), interpolation=cv2.INTER_AREA)
        if first is None:
            first = g
        if prev is not None:
            diffs.append(float(np.abs(g - prev).mean()))
        prev = g
        last = g
        n += 1
    cap.release()
    if n < 2:
        return None
    d = np.array(diffs)
    med = float(np.median(d)) if len(d) else 0.0
    return {"n": n, "first": first, "last": last, "median": med,
            "max": float(d.max()) if len(d) else 0.0,
            "max_at": int(np.argmax(d)) if len(d) else -1,
            "ratio": (float(d.max()) / med) if med > 1e-9 else float("inf")}


def main(argv):
    here = os.path.dirname(os.path.abspath(__file__))
    d = os.path.join(here, "_seg")
    global W
    for k, v in enumerate(argv[1:]):
        if v == "--dir":
            d = argv[1:][k + 1]
        elif v == "--w":
            W = int(argv[1:][k + 1])
    fns = sorted(f for f in os.listdir(d) if f.startswith("seg_") and f.endswith(".mp4"))
    if not fns:
        print("[err] no segs in", d)
        return
    res = []
    print("=== 段内跳帧 (w=%d) ===" % W)
    for f in fns:
        # 每段扫完立刻丢掉像素，只留首/末帧用于接缝
        r = scan_file(os.path.join(d, f), W)
        if r is None:
            print("  %s  EMPTY/UNREADABLE" % f)
            continue
        flag = "FAIL" if r["ratio"] > 3.0 else "ok"
        print("  %s  n=%3d  med=%.4f  max=%.4f@%d  ratio=%.2f  %s"
              % (f, r["n"], r["median"], r["max"], r["max_at"], r["ratio"], flag))
        res.append((f, r))
    print("=== 接缝（前段末帧 vs 后段首帧）===")
    bad = []
    for i in range(len(res) - 1):
        f0, r0 = res[i]
        f1, r1 = res[i + 1]
        seam = float(np.abs(r1["first"] - r0["last"]).mean())
        base = max(r0["median"], r1["median"], 1e-9)
        ratio = seam / base
        flag = "FAIL" if ratio > 3.0 else "ok"
        if ratio > 3.0:
            bad.append((f0, f1, ratio))
        print("  %s→%s  seam=%.4f  base=%.4f  ratio=%.2f  %s"
              % (f0, f1, seam, base, ratio, flag))
    print("=== 汇总: 段数 %d, 接缝 %d, FAIL %d ===" % (len(res), max(len(res) - 1, 0), len(bad)))
    for b in bad:
        print("   BAD SEAM %s → %s  ratio %.2f" % b)


if __name__ == "__main__":
    main(sys.argv)
