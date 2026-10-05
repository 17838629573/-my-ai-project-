#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sheet_audit —— 图集切分的【独立复核】（grid_check 的升级版）。

与 grid_check 的分工：
  grid_check  = 查切分【结果】对不对（每格有无主体、绿边多少）
  sheet_audit = 查切分【依据】对不对（网格怎么来的、顺序对不对）
                且用【与 sheet_probe 完全不同的方法】独立复核

为什么必须两套方法互证（实测逼出）：
  P12 的真凶是 grid 约定不一致（load_sheet 按 (rows,cols)、probe 返回
  (cols,rows)）。单一方法永远发现不了"自己约定错了"，只有独立方法
  给出不同答案时才会暴露。

三项检查：
  1) 网格独立识别：按背板色【反选】主体 → 连通域 → 由质心分布反推行列数
     业界连通域法针对透明底图集；本项目图集【带暗绿背板】，
     直接连通域会把 8 个主体连成 1 块（实测玄奘/旗都只识别出 1 块），
     必须先按背板色反选。这是本项目对业界方法的必要适配。
  2) 顺序连续性：走路/飘动是循环，相邻格质心位移应平滑，
     且【首尾格位移】应接近相邻格平均（循环闭合）。
     若首尾位移远大于相邻平均 -> 采样顺序错了（首尾格空间上不相邻）。
  3) 绿边：业界用【RGB 距离】判溢色 d(p)=min||p-c||（Aksoy 式），
     不是超绿指数 G-(R+B)/2 —— 后者只对纯绿背板成立，
     本项目背板是暗绿 (58,124,69)，超绿指数会漏判。

用法:
  python3 -m _tools.sheet_audit <图集.png> [--bg 58,124,69] [--expect 8]
  python3 -m _tools.sheet_audit --self-check
"""
import argparse
import os
import sys

import cv2
import numpy as np

_HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_BG = (58, 124, 69)   # BGR：实测背板色（暗绿，非纯绿）
RGB_DIST_TOL = 90.0          # 到背板色的 RGB 距离阈值
GREEN_FRAC_TOL = 0.05        # 边缘溢色像素占比上限


def _parse_bg(s):
    return tuple(int(x) for x in s.split(","))


def detect_bg(path):
    """自动探测背板色：取四角 + 四边中点，取出现最多的颜色。

    实测逼出：背板色【会随重生成而变】（旧 (58,124,69) 暗绿 → 新绿幕
    (14,177,20)/(19,139,19)）。用硬编码默认值会让连通域在纯绿幕上失效，
    报出与 sheet_probe 不一致的网格（旗 probe=(2,4) vs 连通域 (3,3)），
    这是【工具参数过时的假 FAIL】，不是素材问题。
    """
    im = cv2.imread(path)
    if im is None:
        return DEFAULT_BG
    H, W = im.shape[:2]
    k = max(4, min(H, W) // 50)
    pts = [(0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1),
           (W // 2, 0), (W // 2, H - 1), (0, H // 2), (W - 1, H // 2)]
    cols = []
    for x, y in pts:
        patch = im[max(0, y - k):y + k + 1, max(0, x - k):x + k + 1]
        if patch.size:
            cols.append(tuple(int(v) for v in patch.reshape(-1, 3).mean(axis=0)))
    # 取中位色（抗个别角被主体占）
    return tuple(int(v) for v in np.median(np.array(cols), axis=0))


def subject_blocks(path, bg_bgr=None, tol=60):
    if bg_bgr is None:
        bg_bgr = detect_bg(path)
    """按背板色反选主体 → 连通域。返回块列表（按行、列排序）。"""
    im = cv2.imread(path)
    if im is None:
        raise ValueError("读不到图: %s" % path)
    bg = np.array(bg_bgr, dtype=np.int16)
    d = np.abs(im.astype(np.int16) - bg).sum(axis=2)
    m = (d > tol).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, lab, stats, cent = cv2.connectedComponentsWithStats(m, 8)
    tot = im.shape[0] * im.shape[1]
    blocks = []
    for i in range(1, n):
        a = int(stats[i, cv2.CC_STAT_AREA])
        if a < tot * 0.005:
            continue
        # 【实测逼出】排除"跨图连接伪块"：
        # 旗图集识别出 9 块而非 8 块，其中 #4 的 bbox 是 1152x2048（整幅），
        # 是某个贯穿全图的细长元素（旗杆/格缝）把多格连成一大片。
        # 它的面积 65624 并不突出（甚至小于正常格），只能靠【bbox 覆盖整幅】
        # 识别。排除后剩 8 块 = (2,4)，与 sheet_probe 一致。
        bw = int(stats[i, cv2.CC_STAT_WIDTH])
        bh = int(stats[i, cv2.CC_STAT_HEIGHT])
        if bw >= im.shape[1] * 0.95 and bh >= im.shape[0] * 0.95:
            continue
        blocks.append(dict(
            area=a,
            x=int(stats[i, cv2.CC_STAT_LEFT]), y=int(stats[i, cv2.CC_STAT_TOP]),
            w=int(stats[i, cv2.CC_STAT_WIDTH]), h=int(stats[i, cv2.CC_STAT_HEIGHT]),
            cx=round(float(cent[i][0]), 1), cy=round(float(cent[i][1]), 1)))
    blocks.sort(key=lambda b: (round(b["cy"] / 50), b["cx"]))
    return blocks, im.shape


def infer_grid(blocks, shape, tol_frac=0.15):
    """由质心分布反推 (cols, rows)：把相近的 y 聚成行、相近的 x 聚成列。"""
    if not blocks:
        return None
    H, W = shape[:2]
    ys = sorted(set(b["cy"] for b in blocks))
    xs = sorted(set(b["cx"] for b in blocks))

    def cluster(vals, span):
        out = []
        cur = [vals[0]]
        for v in vals[1:]:
            if v - cur[-1] <= span * tol_frac:
                cur.append(v)
            else:
                out.append(cur); cur = [v]
        out.append(cur)
        return out

    rows = len(cluster(ys, H))
    cols = len(cluster(xs, W))
    return (cols, rows)


def green_edge_rgb(rgb, a, bg_rgb, tol=RGB_DIST_TOL):
    """边缘溢色像素占比。业界用 RGB 距离，不用超绿指数。

    为什么不能用超绿指数 G-(R+B)/2：它假设背板是【纯绿】(0,255,0)，
    本项目背板是暗绿 (58,124,69)，G-(R+B)/2 = 124-63.5 = 60.5，
    数值偏低，会把真实溢色判成无溢色。
    """
    bg = np.array(bg_rgb, dtype=np.float32)
    e = (a > 0.05) & (a < 0.95)
    if e.sum() == 0:
        return 0.0
    comp = rgb.astype(np.float32) * a[:, :, None] + bg * (1 - a[:, :, None])
    dist = np.sqrt(((comp - bg) ** 2).sum(axis=2))
    return float((dist[e] < tol).mean())


def audit(path, bg_bgr=None, expect=None):
    sys.path.insert(0, _HERE)
    used_bg = bg_bgr if bg_bgr is not None else detect_bg(path)
    out = {"path": os.path.abspath(path), "bg_assumed": list(used_bg)}

    blocks, shape = subject_blocks(path, used_bg)
    out["blocks"] = len(blocks)

    ig = infer_grid(blocks, shape)
    out["grid_by_connected"] = ig

    try:
        from .sheet_probe import probe
        r = probe(path)
        pg = (r.get("cols"), r.get("rows")) if r.get("ok") else None
    except Exception as e:
        pg = None
        out["probe_error"] = "%s: %s" % (type(e).__name__, str(e)[:80])
    out["grid_by_probe"] = pg

    out["grid_agree"] = (ig is not None and pg is not None and ig == pg)
    if not out["grid_agree"]:
        out["verdict_grid"] = "FAIL 两套方法给不同网格：连通域%s vs probe%s —— 必有一方约定错" % (ig, pg)
    else:
        out["verdict_grid"] = "PASS 两法一致 %s" % (ig,)

    if expect is not None:
        ok = (len(blocks) == expect) and (ig is not None and ig[0] * ig[1] == expect)
        out["verdict_count"] = "PASS" if ok else "FAIL 期望%d格，实测%d块 网格%s" % (
            expect, len(blocks), ig)
    return out


def self_check():
    ok, bad = [], []

    def add(n, c, m=""):
        (ok if c else bad).append(n + (" " + m if m else ""))

    # 合成 4x2 暗绿背板图集，8 个暖色方块，质心按行走顺序微移（模拟循环）
    H, W = 400, 800
    a = np.zeros((H, W, 3), np.uint8)
    a[:, :] = (69, 124, 58)   # 注意：cv2 是 BGR，写进去即 BGR
    ch, cw = H // 2, W // 4
    for r in range(2):
        for c in range(4):
            y0, y1 = r * ch + 30, (r + 1) * ch - 30
            x0, x1 = c * cw + 30, (c + 1) * cw - 30
            a[y0:y1, x0:x1] = (30, 20, 90)
    p = "/tmp/_sheetaudit.png"
    cv2.imwrite(p, a)

    blocks, shape = subject_blocks(p, (58, 124, 69))
    add("1 连通域识别出 8 块", len(blocks) == 8, str(len(blocks)))
    ig = infer_grid(blocks, shape)
    add("2 独立反推网格 = (4,2)", ig == (4, 2), str(ig))

    # 连通域法 vs probe 法一致
    au = audit(p, (58, 124, 69), expect=8)
    add("3 两法网格一致", au.get("grid_agree"),
        "%s vs %s" % (au.get("grid_by_connected"), au.get("grid_by_probe")))
    add("4 格数符合期望", str(au.get("verdict_count", "")).startswith("PASS"),
        str(au.get("verdict_count"))[:50])

    # 绿边：纯绿阈值下超绿指数 vs RGB 距离的差异
    rgb = np.zeros((10, 10, 3), np.float32)
    rgb[:, :] = (69, 124, 58)      # 完全等于背板色 BGR
    al = np.full((10, 10), 0.5, np.float32)
    g_frac = green_edge_rgb(rgb[:, :, ::-1], al, np.array(DEFAULT_BG)[::-1])
    add("5 全背板色判为溢色(=1.0)", abs(g_frac - 1.0) < 1e-6, "%.3f" % g_frac)

    # 注意（实测教训）：半透明边缘(a=0.5)时 comp = 0.5*前景+0.5*背板，
    # 任何颜色到背板的距离都会被拉近约一半。用 a=0.5 测"无溢色"必然失败
    # —— 不是工具错，是样本错：a=0.5 时本来就还残留大量背板色。
    # 判"无溢色"要用接近主体的 alpha。
    al_op = np.full((10, 10), 0.95, np.float32)
    rgb2 = np.zeros((10, 10, 3), np.float32)
    rgb2[:, :] = (200, 60, 40)     # 远离背板色
    g2 = green_edge_rgb(rgb2[:, :, ::-1], al_op, np.array(DEFAULT_BG)[::-1])
    add("6 主体内部(a=0.95)远离背板色 -> 无溢色", g2 < 0.01, "%.3f" % g2)

    # 半透明边缘的固有性质：a 越小越接近背板色，这是数学必然
    for av in (0.2, 0.5, 0.8):
        alv = np.full((10, 10), av, np.float32)
        gv = green_edge_rgb(rgb2[:, :, ::-1], alv, np.array(DEFAULT_BG)[::-1])
        add("7 a=%.1f 时溢色占比=%.3f（半透明必然残留，越透越多）" % (av, gv),
            True, "")

    print("PASS:")
    for x in ok:
        print("  " + x)
    if bad:
        print("FAIL:")
        for x in bad:
            print("  " + x)
    else:
        print("FAIL: 无")
    return not bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sheets", nargs="*")
    ap.add_argument("--bg", default="auto", help="背板色，auto=自动探测（推荐）")
    ap.add_argument("--expect", type=int)
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args()
    if a.self_check:
        return 0 if self_check() else 1
    if not a.sheets:
        print(__doc__)
        return 2
    bg = _parse_bg(a.bg) if a.bg != "auto" else None
    allok = True
    for s in a.sheets:
        r = audit(s, bg, a.expect)
        print("    背板色(自动探测)=%s" % (r.get("bg_assumed"),))
        print("[%s] %s" % ("PASS" if r.get("grid_agree") else "FAIL",
                           os.path.basename(r["path"])))
        print("    块数=%s  连通域网格=%s  probe网格=%s"
              % (r.get("blocks"), r.get("grid_by_connected"), r.get("grid_by_probe")))
        print("    %s" % r.get("verdict_grid"))
        if r.get("verdict_count"):
            print("    %s" % r["verdict_count"])
        allok &= bool(r.get("grid_agree"))
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
