"""编码器选型：按实测压缩率选可用的 fourcc

契约: base.codec
  输入: prefer（可选，指定优先 fourcc）
  输出: 可用的 fourcc 字符串；全不可用则回落 "mp4v"
  依赖: cv2
  被依赖: motion.run（to_mp4 / StreamWriter）、tools.exportspec（规范登记）
  约束: 必须放在 base 层——motion 依赖 tools 会违反分层契约
        （层序 tools > tests > showreel > motion > ... > base）；
        ratio 为实测值，换机必须重测，禁止手改

为什么要有这个模块
  导出一直硬编码 mp4v（MPEG-4 Part 2，2000 年前后的编码），而同素材实测
  VP9 可省 18.1%。但「哪个能用」取决于 OpenCV 构建——本机无 avc1/hevc/av01，
  硬编码 avc1 会直接写出失败。故把「可用性探测 + 压缩率排序」做成一次探测、
  全局复用。
"""
import contextlib
import os

# (fourcc, 名称, 相对 mp4v 的体积比, 声称可用, 备注)
# ratio < 1 表示比 mp4v 更省；None 表示无实测数据（不可用或未测）
CODECS = [
    ("mp4v", "MPEG-4 Part 2", 1.000, True, "现用，兼容性最好"),
    ("VP09", "VP9", 0.833, True, "实测 -18.1%，编码较慢"),
    ("MJPG", "Motion JPEG", 2.646, True, "实测 +160%，仅作调试"),
    ("avc1", "H.264", None, False, "本环境 OpenCV 无此编码器"),
    ("hev1", "HEVC", None, False, "本环境无 hevc_v4l2m2m 设备"),
    ("av01", "AV1", None, False, "本环境无编码器"),
]

FALLBACK = "mp4v"


def _probe(tag, w=64, h=64):
    """探测某 fourcc 能否真正打开一个 VideoWriter。"""
    import cv2
    path = "/tmp/_codec_probe.mp4"
    try:
        vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*tag), 24, (w, h))
        ok = bool(vw.isOpened())
        vw.release()
        return ok
    except Exception:
        return False
    finally:
        # 为什么用 suppress 而不是裸 except pass：删除探测临时文件失败（被占用/权限）
        # 属环境噪音，不影响探测结论；但裸 pass 会被 S01 静默异常规则判为吞错，
        # 故显式声明"此处有意忽略且原因已知"。
        with contextlib.suppress(OSError):
            os.remove(path)


def pick_codec(prefer=None):
    """按实测压缩率升序挑选「可用」的 fourcc，越小越省。

    曾因直接按表内书写顺序取首个可用项而永远选中 mp4v（表首），
    等于改造了个寂寞——故此处必须显式排序。
    """
    ranked = sorted([c for c in CODECS if c[2] is not None],
                    key=lambda c: c[2])
    order = ([prefer] if prefer else []) + [c[0] for c in ranked] + [FALLBACK]
    for tag in order:
        if tag and _probe(tag):
            return tag
    return FALLBACK


def ratio_of(tag):
    """返回该 fourcc 的实测体积比；无数据返回 None。"""
    for t, _n, r, _a, _m in CODECS:
        if t == tag:
            return r
    return None
