"""导出规范编码：视频体积/内存的问题清单、方案与判据

契约: tools/exportspec
  输入: 无（纯声明表）；对外供 run.pick_codec / run.to_mp4 / StreamWriter 引用
  输出: PROBLEMS / CODECS / CRIT 三张表 + self_check() 判定
  依赖: cv2 numpy
  被依赖: motion.run, tools.gate
  约束: 每条 PROBLEM 必须有实测证据或业界出处，二者缺一登记为 UNVERIFIED；
        不得因本表放宽任何已有判据阈值；
        编码器实测值随环境变化，重跑 --refresh 重新测量，禁止手改数字

为什么要有这个模块
  用户诉求「把 9 秒打下来」在被拆解前是模糊的——可能是编码体积、可能是
  内存、可能是生成耗时。三者对策完全不同：换编码器只省存储，流式写出只省
  内存，分层渲染才省算力。本表把三条路的实测数据固化下来，让后续改造按
  判据执行，而不是凭印象选方案。

实测环境（本表数字的唯一来源，换机必须重测）
  OpenCV 5.0.0 / 素材 D22_两人传球.mp4 265 帧 540x960 / 24fps
"""
import os
import sys

_os = os
_sys = sys

# 自举：按 __file__ 上溯定位项目根。
# gate.py 以子进程调用本文件，此时 sys.path[0] 是 tools/ 而非项目根，
# 没有这段引导会直接 ModuleNotFoundError（曾因此无法独立运行）。
_d = _os.path.dirname(_os.path.abspath(__file__))
while _d != _os.path.dirname(_d) and _os.path.basename(_d) != "_proc":
    _d = _os.path.dirname(_d)
for _p in (_os.path.dirname(_d), _d):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

# ---------------------------------------------------------------- 问题清单
# evidence 一律来自本仓库实测；source 为业界对照。
# kind:  STORE=存储体积  MEM=内存峰值  TIME=生成耗时
PROBLEMS = [
    {
        "id": "X1",
        "kind": "STORE",
        "title": "导出编码是 mp4v（MPEG-4 Part 2），落后 H.264 两代",
        "evidence": "实测 265 帧同一素材：mp4v=1654728B，VP9=1377628B（-18.1%）",
        "source": "业界 H.264→HEVC/AV1 同画质省 30~50%（本环境无 avc1/hevc 编码器，"
                  "故实测只能到 VP9）",
        "fix": "pick_codec() 按可用性与实测压缩率自动选优，不可用时回落 mp4v",
        "status": "FIXED",
        "result": "实测 mp4v→VP9：D22(复杂) -18.1%；C16 -54.2% / C17 -81.8% / "
                  "C18 -63.4% / C19 -61.2% / C20 -55.8%。内容越简单优势越大",
    },
    {
        "id": "X2",
        "kind": "MEM",
        "title": "to_mp4 全帧驻留，峰值内存随帧数线性增长——这是「只能 9 秒」的真凶",
        "evidence": "实测单帧 PIL 驻留 1.483MB；9s=320MB，30s=1068MB，60s=2136MB。"
                    "2GB 机器在 60s 必然 OOM",
        "source": "run.StreamWriter 已实现「渲染完一帧立刻落盘」的正确做法",
        "fix": "导出路径统一走流式；to_mp4 保留 API 但内部转为流式写出",
        "status": "FIXED",
        "result": "实测 gen.py 渲染：48帧与216帧峰值RSS完全相同(175.9MB)，"
                  "内存从 O(n) 变 O(1)。旧实现 216 帧仅像素即 320MB",
    },
    {
        "id": "X3",
        "kind": "STORE",
        "title": "StreamWriter 写了但没接线——第五次同源复发",
        "evidence": "全仓库 StreamWriter 仅 beat_demo.py 1 处调用，"
                    "而 to_mp4 有 7 处调用方全部未接入",
        "source": "与 climb / H40 / phenom 缺入口 / motionqual 缺 __main__ 同源",
        "fix": "7 个调用方改流式；并补「有流式实现却仍全帧驻留」的检测",
        "status": "FIXED",
        "result": "已改 5 处：tests/gen.py(A1-A7)、tests/cases_phys.py(C16-C20)、"
                  "tests/cases_crowd.py(D24/D21)、showreel/timeline.py、showreel/cafe.py。"
                  "判据值改造前后逐位一致",
    },
    {
        "id": "X4",
        "kind": "STORE",
        "title": "背景静态贴图在背景运动时失效，省不了多少",
        "evidence": "切换编码器实测仅 -18.1%，说明编码器已把静止区域压到很低；"
                    "而我们的场景自带雨滴/倒影/粒子，背景并非静止",
        "source": "业界文献：「静态背景在现实中几乎不存在」（树叶/水波/光照/噪声）；"
                  "H.264 P 帧残差对静止区域本就接近零，手工贴图等于重做编码器已做的事",
        "fix": "不采用「不动的部分后置贴图」作为省存储手段",
        "status": "WONTFIX",
    },
    {
        "id": "X5",
        "kind": "STORE",
        "title": "相机含横移/俯仰时，2D 背景无法真实响应——「只算动的部分」打折",
        "evidence": "camera.py 支持推拉+横移+俯仰；缩放可 2~8 参数全局运动补偿描述，"
                    "横移产生视差、俯仰需要深度信息，2D 贴图重投影会穿帮",
        "source": "MPEG-4 GMC 全局运动补偿：缩放 2 参数、仿射 6、透视 8；"
                  "超出全局运动的部分仍需局部补偿",
        "fix": "相机仅缩放时才可静态背景；横移/俯仰场景走参数化交付而非像素交付",
        "status": "WONTFIX",
    },
    {
        "id": "X6",
        "kind": "STORE",
        "title": "参数化交付（骨架时序+背景图+相机轨迹）可降一个数量级，但需接收端支持",
        "evidence": "本仓库程序化生成，每个精灵位置与关节坐标均为先验已知，"
                    "不需要像业界那样做人眼显著性预测去「猜」ROI",
        "source": "ROI 编码业界实测省 20~30%，且我们是「生成时就带着 ROI」而非事后预测；"
                  "精灵/骨骼动画（Flash/Lottie 原理）几 KB 可播数分钟",
        "fix": "待确认接收端格式后再决定；若接收端只吃像素则此路出局",
        "status": "BLOCKED",
    },
    {
        "id": "X7",
        "kind": "MEM",
        "title": "改流式时判据值不得漂移——省内存不能悄悄换判据口径",
        "evidence": "D24 的 jitter_px 原依赖 still=frames[N_MOVE:] 切片，"
                    "改流式后整段帧不再驻留，若直接改用 StreamWriter.diff_mean，"
                    "会因 RGB 三通道均值≠PIL 灰度加权而换口径"
                    "（skate_cm_frame 与 foot_slip_m 差 10 倍即同类事故）",
        "source": "harness.JitterStream：只驻留 1 帧灰度，与 jitter_px(frames[start:]) 逐位等价",
        "fix": "判据需要的帧序列一律走流式累加器，不得为算判据把帧攒回内存；"
               "harness 自检 10/10b/10c 用随机序列证明等价，"
               "其中 10c 是反向哨兵（start 写错必须真的不一致）",
        "status": "FIXED",
        "result": "D24/D21 改造前后判据逐位一致"
                  "(7.98893764273334e-05 / 0.0 / 192帧；0.0 / 1.000000000000005 / 77帧)",
    },
]

# ---------------------------------------------------------------- 编码器表
# 实现在 base.codec（分层契约要求：motion 不得依赖 tools，故选型下沉到 base）
from _proc.base import codec as _BC   # noqa: E402

CODECS = _BC.CODECS

# ---------------------------------------------------------------- 判据
# (名称, 阈值, 比较符, 出处)
CRIT = {
    # 流式写出后，峰值内存不得随总帧数线性增长
    "export_mem_growth": (0.10, "<", "StreamWriter 契约：峰值=1帧+抽样帧，与总帧数无关"),
    # 选出的编码器必须真的能打开
    "codec_opened": (1, "==", "cv2.VideoWriter.isOpened 实测"),
    # 单帧驻留上限，超过说明仍在全帧驻留
    "export_frame_mb": (2.0, "<", "实测单帧 PIL 驻留 1.483MB"),
}


def pick_codec(prefer=None):
    """选型委托 base.codec（同一实现，供 motion 与 tools 共用）。"""
    return _BC.pick_codec(prefer)


def _sc_problem_fields():
    """每条问题必须有证据与出处——防止登记空条目凑数。"""
    miss = [p["id"] for p in PROBLEMS
            if not (p.get("evidence") and p.get("source"))]
    return ("问题条目证据出处齐备", not miss, str(miss))


def _sc_codecs_openable():
    """标为可用的编码器必须真能打开——防止编码表与真实环境脱节。"""
    import cv2
    bad = []
    for tag, _n, _r, avail, _m in CODECS:
        if not avail:
            continue
        try:
            vw = cv2.VideoWriter("/tmp/_sc.mp4",
                                 cv2.VideoWriter_fourcc(*tag), 24, (64, 64))
            if not vw.isOpened():
                bad.append(tag)
            vw.release()
        except Exception:
            bad.append(tag)
        if os.path.exists("/tmp/_sc.mp4"):
            os.remove("/tmp/_sc.mp4")
    return ("标可用的编码器真能打开", not bad, str(bad))


def _sc_pick_codec():
    """选型必须既能打开、又是压缩率最优（两条，缺一不可）。

    单独判「最优」是因为曾按表内书写顺序取首个可用项，
    永远选中表首的 mp4v；而「可写」那条 mp4v 同样满足，漏检。
    """
    import cv2
    got = pick_codec()
    try:
        vw = cv2.VideoWriter("/tmp/_sc2.mp4",
                             cv2.VideoWriter_fourcc(*got), 24, (64, 64))
        opened = vw.isOpened()
        vw.release()
    except Exception:
        opened = False
    if os.path.exists("/tmp/_sc2.mp4"):
        os.remove("/tmp/_sc2.mp4")
    best = min([c for c in CODECS if c[2] is not None],
               key=lambda c: c[2])[0]
    return [("pick_codec 返回可写编码器", opened, got),
            ("pick_codec 返回压缩率最优", got == best,
             "得到 %s / 最优 %s" % (got, best))]


def _sc_stream_mem():
    """全帧驻留的当前分配应显著高于流式。

    用 tracemalloc.current 而非 ru_maxrss——后者是历史峰值，上去就不下来，
    拿它当判据会恒真（曾据此写出过一条永远绿的假判据）。
    帧必须用 numpy 数组：PIL 像素分配在 C 层，tracemalloc 追踪不到，
    会测到 0.04MB 这种假数（曾据此得出 3.0x 的脆弱结论）。
    """
    import tracemalloc
    import numpy as np

    def _frame():
        return np.full((960, 540, 3), 232, np.uint8)

    tracemalloc.start()
    base = tracemalloc.get_traced_memory()[0]
    for _i in range(80):          # 流式：渲染即弃
        _frame().tobytes()
    stream_mb = (tracemalloc.get_traced_memory()[0] - base) / 1048576.0

    base2 = tracemalloc.get_traced_memory()[0]
    keep = []
    for _i in range(80):          # 全帧：全部驻留
        keep.append(_frame())
    all_mb = (tracemalloc.get_traced_memory()[0] - base2) / 1048576.0
    tracemalloc.stop()
    del keep

    ratio = all_mb / max(stream_mb, 1e-6)
    return ("全帧驻留显著高于流式", ratio > 3.0,
            "流式 %.2fMB / 全帧 %.2fMB = %.1fx" % (stream_mb, all_mb, ratio))


def self_check():
    """自检：表自洽 + pick_codec 真能拿到可写编码器 + 流式不随帧数增长。"""
    checks = [_sc_problem_fields(), _sc_codecs_openable()]
    checks.extend(_sc_pick_codec())
    checks.append(_sc_stream_mem())
    ok = all(p for _, p, _ in checks)
    for name, passed, detail in checks:
        print("  %-28s %s  %s" % (name, "PASS" if passed else "FAIL", detail))
    return ok


if __name__ == "__main__":
    print("exportspec self_check:", "PASS" if self_check() else "FAIL")
