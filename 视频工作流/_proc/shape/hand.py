# 契约: proc/shape/hand
#   一句话: 手部解剖：掌与五指的关节/胶囊，按真实比例与外展角生成
#   完整契约见 shape/__init__.py
"""手：掌 + 五指（末端形体）。

出处（不凭记忆写）：
    手长 = 0.108 × 身高          Drillis & Contini 1966（Winter 1990 转引，Table 1.6）
    指节占手长比例               Regensburg / Buchholz X 光测量 n=71
    最大外展指间角               Med-Science 2023 男性右手（DOAJ）
        拇指-食指 53.94°  食指-中指 19.99°  中指-无名指 17.29°  无名指-小指 27.72°
    相对中指轴换算：拇指 +73.9°  食指 +20.0°  中指 0°  无名指 -17.3°  小指 -45.0°
    放松态取最大外展的 40%（SPLAY_REST，可调参数，非文献值）

设计：手是末端，不参与 IK 链。关节由腕 + 前臂方向推导，
随腕一起走 —— 不会像披帛那样脱离身体。

关节命名（每只手）：
    hand_{s}   整手末端（LOD0 用）
    palm_{s}   掌心
    m{i}_{s} p{i}_{s} d{i}_{s} t{i}_{s}   各指 掌指/近节/中节/指尖
    i = 0 拇指 1 食指 2 中指 3 无名指 4 小指（拇指 3 节，其余 4 节）
"""
import math
import numpy as np

HAND_LEN = 0.108          # 手长 / 身高

# 各指节占手长比例，基→尖（掌骨 → 近节 → 中节 → 远节）
SEG = {
    0: (0.2338, 0.1576, 0.1152),                  # 拇指：无中节
    1: (0.3482, 0.2027, 0.1175, 0.0882),          # 食指
    2: (0.3341, 0.2254, 0.1431, 0.0930),          # 中指
    3: (0.2948, 0.2105, 0.1362, 0.0954),          # 无名指
    4: (0.2781, 0.1672, 0.0956, 0.0843),          # 小指
}

# 相对中指轴的最大外展角（度），拇指为正（朝前），小指为负
FAN_MAX = {0: 73.9, 1: 20.0, 2: 0.0, 3: -17.3, 4: -45.0}
SPLAY_REST = 0.40         # 放松态 = 最大外展的 40%

# 各指关节名：3 节（拇指，无中节）→ m/p/t；4 节 → m/p/d/t
NAMES = {3: ("m", "p", "t"), 4: ("m", "p", "d", "t")}

# 掌指关节横向铺开（沿 拇指→小指 轴，单位=手长）
KNOCK = {0: -0.090, 1: -0.030, 2: 0.0, 3: 0.035, 4: 0.075}

CURL_REST = 0.30          # 放松握曲（弧度/关节）


# ---------------------------------------------------------------- 向量
def _unit(v):
    v = np.asarray(v, dtype=float)
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-9 else np.array([0.0, -1.0, 0.0])


def _perp(v, ref):
    """ref 中垂直于 v 的分量（单位向量）；退化时退回另一参考轴。"""
    v = _unit(v)
    r = np.asarray(ref, dtype=float)
    p = r - v * float(np.dot(r, v))
    if float(np.linalg.norm(p)) < 1e-6:
        p = np.cross(v, np.array([0.0, 0.0, 1.0]))
    return _unit(p)


def _rot_toward(v, target, ang):
    """在 v 与 target 张成的平面内，把 v 朝 target 转 ang 弧度。"""
    v = _unit(v)
    t = _perp(v, target)
    return v * math.cos(ang) + t * math.sin(ang)


# ---------------------------------------------------------------- 姿态
def hand_pose(wri, elb, side="r", hand_len=HAND_LEN, splay=SPLAY_REST,
              curl=None, palm_frac=0.30):
    """由腕与前臂方向推出整只手的关节（归一化坐标，×身高）。

    wri, elb   腕 / 肘 的归一化坐标（v 为竖直）
    curl       {指号: 弧度/关节}，缺省 CURL_REST
    palm_frac  掌心沿手方向的位置（占手长）
    """
    if side not in ("l", "r"):
        raise ValueError("未知手别 %r（应为 l / r）" % side)
    wri = np.asarray(wri, dtype=float)
    d = _unit(wri - np.asarray(elb, dtype=float))     # 手继续沿前臂方向延伸
    fwd = _perp(d, (1.0, 0.0, 0.0))                   # 前向分量（扇开面）
    axis = np.cross(d, fwd)                           # 拇指→小指 轴
    sgn = -1.0 if side == "r" else 1.0                # 左右镜像

    cur = dict(curl or {})
    out = {}
    out["hand_%s" % side] = wri + d * (0.55 * hand_len)
    palm = wri + d * (palm_frac * hand_len)
    out["palm_%s" % side] = palm

    for i in range(5):
        ang = math.radians(FAN_MAX[i] * float(splay))
        dir_i = _unit(d * math.cos(ang) + fwd * math.sin(ang))
        base = palm + axis * (sgn * KNOCK[i] * hand_len)
        c = float(cur.get(i, CURL_REST))
        p, dd = base, dir_i
        names = NAMES[len(SEG[i])]
        for k, frac in enumerate(SEG[i]):
            dd = _rot_toward(dd, -d, c) if k > 0 else dd
            p = p + dd * (frac * hand_len)
            out["%s%d_%s" % (names[k], i, side)] = p
    return out


def attach(J, hand_lod=1, curl=None, hand_len=HAND_LEN, splay=SPLAY_REST):
    """把两只手挂到姿态 J 上，返回新 dict（不改动入参）。"""
    out = dict(J)
    for s in ("l", "r"):
        w, e = "wri_%s" % s, "elb_%s" % s
        if w in out and e in out:
            out.update(hand_pose(out[w], out[e], s,
                                 hand_len=hand_len, splay=splay,
                                 curl=(curl or {}).get(s)))
    return out


# ---------------------------------------------------------------- 胶囊
def _chain(i, s):
    names = NAMES[len(SEG[i])]
    return ["palm_%s" % s] + ["%s%d_%s" % (nm, i, s) for nm in names]


def caps(lod, s, region="skin"):
    """手的胶囊表 [(a, b, r, region)]，r 为归一化半径（×身高）。

    LOD 0  整手一团（Khronos：单胶囊最便宜，多数场景够用）
    LOD 1  掌 + 每指两段（看得见五指）
    LOD 2  全指节（特写 / 敲击 / 抓握）
    """
    R = {0: 0.030, 1: 0.026, 2: 0.012, 3: 0.0095, 4: 0.0090, 5: 0.0085}
    if lod <= 0:
        return [("wri_%s" % s, "hand_%s" % s, R[0], region)]
    out = [("wri_%s" % s, "palm_%s" % s, R[1], region)]
    for i in range(5):
        seq = _chain(i, s)
        if lod == 1:
            a, b = seq[0], seq[-1]                  # 掌 → 指尖，两段
            out.append((a, seq[1], R[2], region))
            out.append((seq[1], b, R[3], region))
        else:
            for k in range(len(seq) - 1):
                out.append((seq[k], seq[k + 1],
                            R[2] if k == 0 else (R[3] if k == 1 else R[4]),
                            region))
    return out


def joints(lod, s):
    """该 LOD 需要的关节名（用于模板登记）。"""
    if lod <= 0:
        return ["hand_%s" % s]
    out = ["palm_%s" % s]
    for i in range(5):
        out += ["%s%d_%s" % (nm, i, s) for nm in NAMES[len(SEG[i])]]
    return out


# ---------------------------------------------------------------- 自检
if __name__ == "__main__":
    ok = True

    def chk(n, c, e=""):
        global ok
        ok = ok and bool(c)
        print("  %-24s %s %s" % (n, "OK" if c else "FAIL", e))

    wri = np.array([0.0, 0.4905, -0.1106])
    elb = np.array([0.0, 0.6365, -0.1106])
    P = hand_pose(wri, elb, "r")

    chk("手长比例", abs(HAND_LEN - 0.108) < 1e-9, "0.108×身高")
    chk("关节齐全", len(P) == 1 + 1 + 3 + 4 * 4, "%d 个" % len(P))
    chk("五指都有指尖", all("t%d_r" % i in P for i in range(5)))

    lv = [float(np.linalg.norm(P["t%d_r" % i] - P["palm_r"])) for i in range(5)]
    chk("中指最长", lv[2] == max(lv), "中=%.4f 小=%.4f" % (lv[2], lv[4]))
    chk("拇指短于食指", lv[0] < lv[1], "拇=%.4f 食=%.4f" % (lv[0], lv[1]))
    chk("指尖在手掌下方", P["t2_r"][1] < P["palm_r"][1])

    f0 = P["m0_r"] - P["palm_r"]
    f4 = P["m4_r"] - P["palm_r"]
    chk("拇指与小指分列两侧",
        float(np.dot(f0, f4)) < 0 or abs(f0[0] - f4[0]) > 1e-4,
        "u 向 %.4f / %.4f" % (f0[0], f4[0]))

    a = hand_pose(wri, elb, "r", curl={1: 0.05})
    b = hand_pose(wri, elb, "r", curl={1: 0.90})
    ext = float(np.linalg.norm(a["t1_r"] - a["m1_r"]))
    flx = float(np.linalg.norm(b["t1_r"] - b["m1_r"]))
    chk("弯曲后指尖回收", flx < ext, "伸 %.4f → 屈 %.4f" % (ext, flx))

    c0 = caps(0, "r")
    c1 = caps(1, "r")
    c2 = caps(2, "r")
    chk("LOD 胶囊数递增", len(c0) < len(c1) < len(c2),
        "%d / %d / %d" % (len(c0), len(c1), len(c2)))
    chk("LOD2 含全指节", len(c2) == 1 + 3 + 4 * 4, "%d" % len(c2))

    J = {"wri_r": wri, "elb_r": elb, "wri_l": wri, "elb_l": elb}
    J2 = attach(J, 1)
    chk("attach 不改动入参", "palm_r" not in J)
    chk("attach 双手", "t0_r" in J2 and "t0_l" in J2)
    try:
        hand_pose(wri, elb, "x")
        chk("未知手别报错", False)
    except ValueError:
        chk("未知手别报错", True)

    print("=" * 52)
    print("  hand 自检 %s" % ("PASS" if ok else "FAIL"))
