#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q_a 冻结 / 重复帧检测。

标准依据：EBU QC 0044B《Video Freeze》v2.0
  - 定义：多个相邻【相同 or 近似相同】帧
  - 参数：Minimum Duration（默认 25 帧）、Maximum Duration（50）、
          Similarity Threshold（示例 0.85）、Ignore Black
  - 已知陷阱（标准里明确写了）：
    1) 编码后像素常常【不完全相同】，不能用零阈值
    2) 静态场景会被误报 —— 必须与"该镜头本应有运动"区分
    3) <2 帧的 freeze 通常不可感知，应丢弃

学术论文补充：FD(i) = MEAN((Y(i+1)-Y(i))^2)，用非零阈值；
  并用归一化帧间相关系数 ρk 区分静态/冻结。
"""
import numpy as np
from .qc_common import frame_diff_sq, pearson

# 默认阈值（EBU 0044B 的量级，按 fps 换算）
DEFAULT_MIN_FRAMES = 2      # <2 帧不可感知，丢弃
DEFAULT_SIM_THRESH = 0.85   # EBU 示例值
# 双阈值：只看 rho 会误判【平滑运动】—— 缓慢平移的相邻帧 rho 天然很高
# （实测：正弦纹理 3px/帧平移，rho=0.935 > 0.85，整段被误报为冻结）。
# 真冻结的 FD≈0（编码噪声级），平滑运动 FD 虽小但非零。
# 故必须叠加 FD 判据：fd <= max(FD_ABS, 该序列中位 FD * FD_REL)
DEFAULT_FD_ABS = 1e-5
DEFAULT_FD_REL = 0.10


class _Events(list):
    """事件列表，附带 .thresh（本次判定用的阈值）。"""
    thresh = {}


def detect(src, min_frames=DEFAULT_MIN_FRAMES,
           sim_thresh=DEFAULT_SIM_THRESH, ignore_black=True,
           black_luma=0.02, fd_abs=DEFAULT_FD_ABS, fd_rel=DEFAULT_FD_REL):
    """返回冻结段列表（list）。每段 {start, end, frames, mean_rho, mean_fd}

    判据：rho >= sim_thresh 且 fd <= max(fd_abs, median_fd * fd_rel)
    先扫一遍算全序列中位 FD 作为相对基准。
    """
    n = len(src)
    if n < 2:
        return []
    # 预扫：算全序列的 rho / fd，用于中位基准
    rhos, fds = [], []
    for i in range(n - 1):
        a, b = src.gray(i), src.gray(i + 1)
        rhos.append(pearson(a, b))
        fds.append(frame_diff_sq(a, b))
    med_fd = float(np.median(fds)) if fds else 0.0
    fd_thresh = max(fd_abs, med_fd * fd_rel)

    events = []
    run = None

    def close(run, end_idx):
        if run is None:
            return None
        frames = end_idx - run[0] + 1
        if frames < min_frames:
            return None          # <2 帧不可感知
        return {"start": run[0], "end": end_idx, "frames": frames,
                "mean_rho": float(np.mean(run[1])),
                "mean_fd": float(np.mean(run[2]))}

    for i in range(n - 1):
        a, b = src.gray(i), src.gray(i + 1)
        rho = rhos[i]
        fd = fds[i]
        # 忽略黑帧（EBU 默认 true）
        if ignore_black and (a.mean() < black_luma and b.mean() < black_luma):
            e = close(run, i - 1); run = None
            if e: events.append(e)
            continue
        if rho >= sim_thresh and fd <= fd_thresh:
            if run is None:
                run = (i, [], [])
            run[1].append(rho); run[2].append(fd)
        else:
            e = close(run, i); run = None
            if e: events.append(e)
    e = close(run, n - 1)
    if e: events.append(e)
    # 阈值信息用子类属性携带，不塞进 events 列表
    # （塞进去会污染 len(events)，自检第 1/4/5/6 项因此误判）
    out = _Events(events)
    out.thresh = {"sim": sim_thresh, "fd": fd_thresh, "med_fd": med_fd,
                  "fd_abs": fd_abs, "fd_rel": fd_rel}
    return out


def score(events, total_frames):
    """冻结占比 = 冻结帧数 / 总帧数。比例过高 = 视频卡顿。"""
    real = list(events)
    froze = sum(e["frames"] for e in real)
    return {"events": real,
            "thresh": getattr(events, "thresh", {}),
            "frozen_frames": froze,
            "total_frames": int(total_frames),
            "ratio": froze / float(total_frames) if total_frames else 0.0}


def self_check():
    """用合成序列验证：造一段中间有 5 帧重复的序列。"""
    import tempfile, os
    ok, bad = [], []
    def add(n, c, m=""):
        (ok if c else bad).append(n + (" " + m if m else ""))

    class Fake:
        def __init__(self, frames): self.f = frames
        def __len__(self): return len(self.f)
        def gray(self, i): return self.f[i]

    rng = np.random.default_rng(0)
    base = [rng.random((32, 32)) for _ in range(10)]
    # 第 10..14 帧重复（冻结 5 帧）
    seq = base + [base[-1].copy() for _ in range(5)] + \
          [rng.random((32, 32)) for _ in range(10)]
    ev = detect(Fake(seq), min_frames=2, sim_thresh=0.85)
    add("1 检出冻结段", len(ev) == 1, "段数=%d" % len(ev))
    add("1b 阈值信息在 .thresh 上", hasattr(ev, "thresh") and "fd" in ev.thresh,
        str(getattr(ev, "thresh", {}))[:60])
    if ev:
        add("2 冻结位置正确", ev[0]["start"] == 9, "start=%d" % ev[0]["start"])
        add("3 冻结长度>=5", ev[0]["frames"] >= 5, "frames=%d" % ev[0]["frames"])
    # 纯随机序列不该报冻结
    rnd = [rng.random((32, 32)) for _ in range(20)]
    ev2 = detect(Fake(rnd), min_frames=2, sim_thresh=0.85)
    add("4 随机序列零误报", len(ev2) == 0, "段数=%d" % len(ev2))
    # min_frames 门槛：重复 1 次 = 2 个相邻帧相同
    #   EBU 语义下 min_frames=2 时它【应该】报出（2 帧是最小可计单位）
    #   要用门槛滤掉它，须把 min_frames 提到 3 —— 这才是"丢弃短冻结"的正确用法
    s3 = base[:5] + [base[4].copy()] + [rng.random((32, 32))]
    ev3 = detect(Fake(s3), min_frames=2, sim_thresh=0.99)
    add("5 min_frames=2 时 2 帧冻结应报出", len(ev3) == 1, "段数=%d" % len(ev3))
    ev4 = detect(Fake(s3), min_frames=3, sim_thresh=0.99)
    add("6 提门槛到 3 后可滤除", len(ev4) == 0, "段数=%d" % len(ev4))
    # 7 平滑运动不得误报（rho 高但 fd 非零）—— 只看 rho 会整段误判
    xs = np.arange(64)[None, :]
    smooth = [(0.5 + 0.35 * np.sin((xs + i * 3) * 0.12) *
               np.cos(np.arange(64)[:, None] * 0.10))
              for i in range(30)]
    r5 = detect(Fake(smooth), min_frames=2, sim_thresh=0.85)
    add("7 平滑平移不误报", len([e for e in r5 if "frames" in e]) == 0,
        "段数=%d" % len([e for e in r5 if "frames" in e]))
    # 8 真冻结仍要检出（同样的平滑纹理 + 中间插重复帧）
    sm2 = list(smooth)
    sm2[15:21] = [smooth[15] for _ in range(6)]
    r6 = [e for e in detect(Fake(sm2), min_frames=2, sim_thresh=0.85)
          if "frames" in e]
    add("8 平滑纹理中的真冻结仍检出", len(r6) >= 1, "段数=%d" % len(r6))

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
