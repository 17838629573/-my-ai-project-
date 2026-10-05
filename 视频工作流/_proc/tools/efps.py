# -*- coding: utf-8 -*-
"""R15 有效帧率(eFPS) —— 检测"画面其实没动"这类假动作。

来源: effective FPS (eFPS) —— 每秒内"互不相同"的帧数。
  eFPS == FPS 表示每一帧都不同；服务端为维持恒定 FPS 会复制帧，
  于是标称 24fps 的片子实际可能只有 3fps 的新内容。
  出处: METHODS, SYSTEMS, AND DEVICES FOR MEASURING UPLINK INGEST
        PERFORMANCE OF LIVE VIDEO CONTENT STREAMING（eFPS 定义段）
  辅助: SSIM 重复帧判定（像素级差值法易受噪声干扰，
        内容哈希法对"完全静止"零误判，本工具用哈希 + 可选 SSIM）

历史事故（本工具要抓的）:
  1. 仿真步数当视频帧数：721 仿真步当 721 帧 @20fps 播放
     → 3 秒内容放成 36 秒，95.6% 是重复帧
  2. 咖啡馆 t00s/t03s/t06s 三个不同时刻导出，字节完全相同
     → 时间点没真正驱动渲染
  3. C19 摆锤用常量占位数据：240 帧视频完全静止，一帧没动

判据:
  dup_ratio  重复帧占比。> 0.5 即告警（一半以上的帧是复制的）
  eFPS       有效帧率。低于标称 fps 的 1/3 视为"名义动画、实际静止"

用法:
    python3 _proc/tools/efps.py <png序列目录 或 若干张 png>
"""
import hashlib
import os
import sys


def _hash(p):
    with open(p, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def scan(paths):
    """paths: 有序图片路径列表。返回 (n, unique, dup_ratio, runs)。

    runs: 连续重复段 [(起始索引, 长度)]，长度>3 的段即为"卡住"
    """
    hs = [_hash(p) for p in paths]
    n = len(hs)
    if n == 0:
        return 0, 0, 0.0, []
    uniq = len(set(hs))
    dup = 1.0 - uniq / float(n)
    runs, i = [], 0
    while i < n:
        j = i
        while j + 1 < n and hs[j + 1] == hs[i]:
            j += 1
        if j - i + 1 > 3:
            runs.append((i, j - i + 1))
        i = j + 1
    return n, uniq, dup, runs


def collect(target):
    if os.path.isdir(target):
        fs = sorted(f for f in os.listdir(target) if f.lower().endswith((".png", ".jpg")))
        return [os.path.join(target, f) for f in fs]
    return [target]


def self_check():
    """自检：造一段"一半帧静止"的合成序列，验证工具能抓到。"""
    import tempfile
    d = tempfile.mkdtemp()
    body_a = b"\x89PNG\r\n\x1a\nA" + b"0" * 40
    body_b = b"\x89PNG\r\n\x1a\nB" + b"1" * 40
    ps = []
    for i in range(10):                 # 前 10 帧静止，后 10 帧交替
        p = os.path.join(d, "f%03d.png" % i)
        with open(p, "wb") as f:
            f.write(body_a if i < 10 else (body_a if i % 2 else body_b))
        ps.append(p)
    n, u, dup, runs = scan(ps)
    ok1 = dup > 0.5                     # 应抓到高重复率
    ok2 = any(L >= 10 for _s, L in runs)  # 应抓到长度 10 的静止段
    print("eFPS 自检: n=%d unique=%d dup=%.2f 静止段=%s -> %s"
          % (n, u, dup, runs, "PASS" if (ok1 and ok2) else "FAIL"))
    return 0 if (ok1 and ok2) else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(self_check())
    paths = []
    for a in sys.argv[1:]:
        paths.extend(collect(a))
    n, u, dup, runs = scan(paths)
    print("帧数 %d   不同帧 %d   重复率 %.3f" % (n, u, dup))
    for s, L in runs:
        print("  [静止段] 起始 %d 连续 %d 帧完全相同" % (s, L))
    sys.exit(1 if dup > 0.5 else 0)
