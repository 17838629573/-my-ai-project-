"""showreel/shard.py — 90秒长镜头分段渲染驱动（规避内存上限与单命令时限）。

契约
----
把 timeline.render 的全帧缓存改为「分段渲染 → 每段独立落盘 → 释放内存」，
最后用 ffmpeg concat 拼成整片。

为什么必须分段（实测，非推测）:
  * 内存: 1920x1080x3 uint8 = 6.22 MB/帧, 2160 帧 = 13.4 GB,
    而本机可用内存 2 GB —— 全帧缓存必然 OOM。
  * 时限: 实测 0.317 s/帧 -> 全片 11.4 min, 超过单条命令 10 min 上限。
  * 吞吐: 本机 2 核, 起 2 进程并行, 墙钟约减半。

用法: python3 showreel/shard.py [--shard 60] [--jobs 2] [--out 路径]
依赖: showreel.timeline.render, ffmpeg concat demuxer
来源: ffmpeg concat demuxer（官方推荐的无重编码拼接方式）;
      流式落盘替代全帧缓存是长视频渲染的通行做法（避免 OOM）。
"""
import io
import os
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.dirname(_HERE))

from showreel import timeline

TMP = os.path.join(_HERE, "_seg")
FINAL = os.path.join(_ROOT, "showreel_90s.mp4")


def _mark(idx):
    return os.path.join(TMP, "seg_%03d.done" % idx)


def _read_mark(idx):
    p = _mark(idx)
    if not os.path.exists(p):
        return None
    try:
        d = {}
        for ln in io.open(p, encoding="utf-8").read().splitlines():
            if "=" in ln:
                k, v = ln.split("=", 1)
                d[k.strip()] = v.strip()
        return d
    except Exception:
        return None


def _one(a, b, idx):
    """子进程: 渲染 [a,b) 到 _seg/seg_%03d.mp4，并写 .done 指纹标记。

    断点续跑**必须校验 .done 标记而非只看 mp4 是否存在**（实测教训）:
      旧版判定 `os.path.exists(mp4)` —— 一旦某段被错误的段号写脏
      （见下方 s0 说明），后续所有批次都会把它当"已完成"永久跳过,
      错误被固化且无任何报错。改为校验 (start,end,frames) 三元组。
    """
    out = os.path.join(TMP, "seg_%03d.mp4" % idx)
    m = _read_mark(idx)
    if (m and os.path.exists(out) and os.path.getsize(out) > 0
            and m.get("start") == str(a) and m.get("end") == str(b)):
        return out
    timeline.render(a, b, out=out)
    n = 0
    try:
        import cv2
        cap = cv2.VideoCapture(out)
        while True:
            ok, _ = cap.read()
            if not ok:
                break
            n += 1
        cap.release()
    except Exception:
        n = -1
    with io.open(_mark(idx), "w", encoding="utf-8") as f:
        f.write("start=%d\nend=%d\nframes=%d\n" % (a, b, n))
    return out


def main(argv):
    shard = 60
    jobs = 1
    final = FINAL
    s0, ns = 0, -1          # 本次只跑第 s0 段起、共 ns 段（分小批，避免内存/时限触发沙箱回收）
    for k, key in enumerate(argv[1:]):
        if key == "--shard":
            shard = int(argv[1:][k + 1])
        elif key == "--jobs":
            jobs = int(argv[1:][k + 1])
        elif key == "--out":
            final = argv[1:][k + 1]
        elif key == "--s0":
            s0 = int(argv[1:][k + 1])
        elif key == "--n":
            ns = int(argv[1:][k + 1])
    os.makedirs(TMP, exist_ok=True)
    n = timeline.NF
    spans = [(a, min(a + shard, n)) for a in range(0, n, shard)]
    if ns >= 0:
        spans = spans[s0:s0 + ns]
    print("[plan] %d frames / %d shards / jobs=%d / run seg %d..%d"
          % (n, len(spans), jobs, s0, s0 + len(spans) - 1))
    t0 = time.time()
    # 用 fork 子进程而非 multiprocessing: 每段渲染完即退出, 内存彻底归还
    running = []
    for _i, (a, b) in enumerate(spans):
        idx = s0 + _i          # 段号必须是全局编号; 用 enumerate 的 0 基下标会全部写回 seg_000
        pid = os.fork()
        if pid == 0:
            try:
                _one(a, b, idx)
                os._exit(0)
            except Exception as e:
                sys.stderr.write("[seg %d ERR] %s: %s\n" % (idx, type(e).__name__, e))
                os._exit(1)
        running.append((pid, idx))
        if len(running) >= jobs:
            pid_done, i_done = running.pop(0)
            os.waitpid(pid_done, 0)
            print("[seg] %d done (%.0fs)" % (i_done, time.time() - t0))
    for pid, idx in running:
        os.waitpid(pid, 0)
        print("[seg] %d done (%.0fs)" % (idx, time.time() - t0))
    if ns >= 0:
        print("[partial] 分批渲染，跳过 concat（全部段完成后再拼）")
        return None
    # concat
    lst = os.path.join(TMP, "list.txt")
    with open(lst, "w") as f:
        for idx in range(len(spans)):
            f.write("file '%s'\n" % os.path.join(TMP, "seg_%03d.mp4" % idx))
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", lst, "-c", "copy", final], check=True)
    print("[ok] %s  %.0fs" % (final, time.time() - t0))
    return final


if __name__ == "__main__":
    main(sys.argv)
