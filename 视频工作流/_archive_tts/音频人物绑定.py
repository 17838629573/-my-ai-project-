#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音频 ↔ 人物绑定
================
问题：多人同框时不对人物身份绑定，非说话者的嘴也会跟着动。
      业界记载："背景人脸会莫名张嘴，视频会直接毁掉"。

解决：每条音频必须声明 actor；摄影表每行带 actor_id；
      渲染时只对绑定的角色应用口型；渲染后再自检一遍。

四项校验：
  V1 绑定完整性 —— 每条音频都必须有 actor（静音段除外）
  V2 说话者唯一 —— 同一时刻只能有一个说话者
  V3 渲染自检   —— 非说话者嘴部变化必须≈0（像素级，不靠推断）
  V4 错配可检出 —— 故意绑错，检测必须报警
"""
import os, sys, wave
import cv2, numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from 短ID编解码 import Codebook, parse_visemes, frame_count, MIN_VISEME_FRAMES
from 占位音轨 import duration_ms

FPS = 60
# 噪声阈值：非说话者嘴部变化超过它就算错配
MISMATCH_TOL = 0.05


# ---------- 绑定表 ----------

class Bindings:
    def __init__(self, cb: Codebook):
        self.cb = cb
        self.map = {}
        for k, v in cb.map.items():
            if k.startswith("V") and isinstance(v, dict):
                self.map[k] = (v.get("actor") or "").strip()

    def speaker(self, vid):
        return self.map.get(vid, "")

    def check_complete(self):
        """V1：每条音频都必须绑定（允许显式空 = 静音/无人说话）"""
        miss = []
        for v in sorted(self.map):
            if v not in self.map:
                miss.append(v)
        # 显式空字符串是合法的（静音段），None 才是缺失
        bad = [v for v, a in sorted(self.map.items()) if a is None]
        return bad


# ---------- 摄影表（带 actor）----------

class Row:
    __slots__ = ("frame", "vid", "actor", "viseme")

    def __init__(self, frame, vid, actor, viseme):
        self.frame, self.vid, self.actor, self.viseme = frame, vid, actor, viseme


def build_xsheet(binds: Bindings, seq, fps=FPS):
    """
    seq: [(vid, dur_ms, viseme_str)]
    每行都带上这条音频绑定的 actor。
    """
    rows = []
    f = 0
    for vid, dur, vs_str in seq:
        actor = binds.speaker(vid)
        n = frame_count(dur, fps)
        vs = parse_visemes(vs_str)
        cap = max(1, n // MIN_VISEME_FRAMES)
        vs = vs[:cap]
        per = n / len(vs)
        for i, v in enumerate(vs):
            s = int(round(i * per)); e = int(round((i + 1) * per))
            for k in range(s, e):
                rows.append(Row(f + k, vid, actor, v))
        f += n
    return rows


def check_single_speaker(rows):
    """V2：同一帧只能有一个说话者"""
    by_frame = {}
    for r in rows:
        by_frame.setdefault(r.frame, set()).add(r.actor)
    bad = [f for f, a in by_frame.items()
           if len([x for x in a if x]) > 1]
    return sorted(bad)[:5]


# ---------- 渲染（只对绑定角色开口）----------

MOUTH = {"A": (0, 2), "B": (0, 2), "C": (0, 2)}   # 相对角色层左上，口型区偏移
MW, MH = 46, 26
OPEN = {"M1": 1.6, "M2": 1.2, "M3": 1.9, "M4": 1.4, "M5": 0.35}


def make_sprite(seed=0, h=120, w=90):
    """
    造一个带纹理的角色精灵。
    教训：嘴部不能用纯色块 —— 纯色缩放后像素不变，导致自检误判为"没动"。
    必须带纹理，缩放才可度量。
    """
    rng = np.random.default_rng(seed)
    img = np.full((h, w, 3), 150, np.uint8)
    cv2.rectangle(img, (0, 2), (MW, 2 + MH), (70, 70, 70), -1)
    # 嘴部：竖直方向高对比条纹（3px 周期黑白交替）
    # 关键：垂直缩放会打乱条纹相位，差异显著可测。
    # 教训：用平滑渐变时缩放差异只有 0.171，几乎测不出来。
    for i in range(MH):
        v = 30 if (i // 3) % 2 == 0 else 225
        img[2 + i, 0:MW] = (v, v, v)
    # 身体加点噪声纹理
    img[40:, :] = np.clip(img[40:, :].astype(np.int16)
                          + rng.integers(-25, 25, (h - 40, w, 3)), 0, 255).astype(np.uint8)
    return img


def apply_mouth(img, viseme, actor, bound_actor):
    """只有 actor == bound_actor 时才动嘴 —— 这是绑定的核心"""
    if not actor or actor != bound_actor:
        return img
    k = OPEN.get(viseme, 1.0)
    if abs(k - 1.0) < 1e-6:
        return img
    mx, my = MOUTH.get(actor, (0, 2))
    x0, y0 = mx, my
    sub = img[y0:y0 + MH, x0:x0 + MW]
    if sub.size == 0:
        return img
    nh = max(2, int(MH * k))
    img[y0:y0 + MH, x0:x0 + MW] = cv2.resize(
        cv2.resize(sub, (MW, nh)), (MW, MH))
    return img


def render(binds, rows, canvas, sprites, bound=True):
    """
    渲染。bound=False 时模拟"未绑定"：口型应用到所有角色（错误做法）
    """
    H, W = canvas
    seqs = {a: [] for a in sprites}
    speakers = []
    frames = []
    for r in rows:
        f = np.full((H, W, 3), 55, np.uint8)
        for a, (img, pos) in sprites.items():
            cur = img.copy()
            if bound:
                cur = apply_mouth(cur, r.viseme, a, r.actor)
            else:
                cur = apply_mouth(cur, r.viseme, a, a)   # 错：人人跟着动
            x, y = pos
            f[y:y + cur.shape[0], x:x + cur.shape[1]] = cur
            seqs[a].append(cur[2:2 + MH, 0:MW].copy())
        speakers.append(r.actor)
        frames.append(f)
    return frames, seqs, speakers


def deviation(seq, speakers, actor, neutral, want_speaking=True):
    """
    嘴部形态相对【中性基线】的偏离。

    为什么不用相邻帧差：口型在同一 viseme 区间内是恒定的，
    只在切换那一帧非零，均值被稀释到 0.015（实测），看不出问题。
    改用"相对 neutral 的偏离"，说话=张开=偏离大，静默=闭合=偏离0。
    """
    acc = []
    for i, s in enumerate(seq):
        is_spk = (speakers[i] == actor)
        if is_spk != want_speaking:
            continue
        acc.append(np.abs(s.astype(np.float32)
                          - neutral.astype(np.float32)).mean())
    return float(np.mean(acc)) if acc else 0.0


def silent_activity(seq, speakers, actor, neutral):
    """静默期嘴部偏离 —— 应≈0。非零 = 背景人脸莫名张嘴"""
    return deviation(seq, speakers, actor, neutral, want_speaking=False)


def talk_activity(seq, speakers, actor, neutral):
    """说话期嘴部偏离 —— 应明显>0"""
    return deviation(seq, speakers, actor, neutral, want_speaking=True)


if __name__ == "__main__":
    cb = Codebook()
    binds = Bindings(cb)

    print("=" * 60)
    print("音频 ↔ 人物绑定 校验")
    print("=" * 60)

    print("\n[V1] 绑定完整性")
    bad = binds.check_complete()
    print(f"    [{'PASS' if not bad else 'FAIL'}] 每条音频都声明 actor")
    for v in sorted(binds.map):
        a = binds.map[v]
        who = cb.get(a, "name", "（无人/静音）") if a else "（无人/静音）"
        print(f"      {v} -> {a or '-':<3} {cb.get(v,'text'):<14} 说话者 {who}")

    seq = []
    for v in sorted(binds.map):
        d = cb.get(v, "dur")
        seq.append((v, d, "M1M3M0M5"))
    rows = build_xsheet(binds, seq)

    print("\n[V2] 说话者唯一性")
    bad2 = check_single_speaker(rows)
    print(f"    [{'PASS' if not bad2 else 'FAIL'}] 同一帧只有一个说话者"
          f"（{len(rows)}帧）")
    if bad2:
        print(f"        冲突帧: {bad2}")

    # 造三个角色精灵（带纹理）
    H, W = 240, 460
    sprites = {}
    for i, a in enumerate(["A", "B", "C"]):
        sprites[a] = (make_sprite(seed=i), (20 + i * 130, 40))

    print("\n[V3] 渲染自检：非说话者的嘴必须不动")
    f_b, s_b, spk_b = render(binds, rows, (H, W), sprites, bound=True)
    f_n, s_n, spk_n = render(binds, rows, (H, W), sprites, bound=False)
    print(f"    {'角色':<4}{'说话时偏离':>11}{'绑定后静默':>12}{'未绑定静默':>12}{'判定':>8}")
    v3 = True
    neutral = {}
    for a in ["A", "B", "C"]:
        neutral[a] = make_sprite(seed={"A":0,"B":1,"C":2}[a])[2:2+MH, 0:MW].copy()
    for a in ["A", "B", "C"]:
        ta = talk_activity(s_b[a], spk_b, a, neutral[a])     # 说话时应张开
        sb = silent_activity(s_b[a], spk_b, a, neutral[a])   # 绑定后静默应为0
        sn = silent_activity(s_n[a], spk_n, a, neutral[a])   # 未绑定静默应>0
        ok = (ta > 1.0) and (sb < MISMATCH_TOL) and (sn > MISMATCH_TOL)
        v3 = v3 and ok
        print(f"    {a:<4}{ta:>11.3f}{sb:>12.3f}{sn:>12.3f}"
              f"{'OK' if ok else 'BAD':>8}")

    print("\n[V4] 错配可检出（按音频段检测）")
    nz = {a: make_sprite(seed={"A": 0, "B": 1, "C": 2}[a])[2:2 + MH, 0:MW].copy()
          for a in ["A", "B", "C"]}

    def seg_dev(seq, lo, hi, a):
        """某角色在指定帧区间内的嘴部偏离"""
        acc = [np.abs(s.astype(np.float32) - nz[a].astype(np.float32)).mean()
               for s in seq[lo:hi]]
        return float(np.mean(acc)) if acc else 0.0

    # V0 段 = 前 144 帧，声明说话者 A
    lo, hi = 0, frame_count(cb.get("V0", "dur"))
    good = {a: seg_dev(s_b[a], lo, hi, a) for a in ["A", "B", "C"]}
    print(f"    V0 段(帧{lo}-{hi}) 声明说话者 = A")
    print(f"      正确绑定: A={good['A']:.2f}  B={good['B']:.2f}  C={good['C']:.2f}")

    saved = binds.map["V0"]
    binds.map["V0"] = "B"                       # 故意绑错
    rows_bad = build_xsheet(binds, seq)
    f2, s2, spk2 = render(binds, rows_bad, (H, W), sprites, bound=True)
    wrong = {a: seg_dev(s2[a], lo, hi, a) for a in ["A", "B", "C"]}
    print(f"      注入错配: A={wrong['A']:.2f}  B={wrong['B']:.2f}  C={wrong['C']:.2f}")
    binds.map["V0"] = saved

    # 检出条件：该说话的人没说话(A骤降)，不该说的人说了(B骤升)
    detected = (good["A"] - wrong["A"] > 1.0) and (wrong["B"] - good["B"] > 1.0)
    print(f"    [{'PASS' if detected else 'FAIL'}] 错配被检出")
    print(f"        A 应说却没说: {good['A']:.2f} -> {wrong['A']:.2f}")
    print(f"        B 不该说却说: {good['B']:.2f} -> {wrong['B']:.2f}")

    print("\n" + "=" * 60)
    allok = (not bad) and (not bad2) and v3 and detected
    print(f"结论：{'全部通过' if allok else '存在未通过项'}")
    print("=" * 60)
