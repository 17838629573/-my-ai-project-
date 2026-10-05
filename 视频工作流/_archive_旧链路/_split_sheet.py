"""合图切分：网格定序 + 连通域定界（铁律44）

【为什么不是纯硬切】besthub《GPT-Images 精灵指南》原文：
  Poses overflow the cell boundaries. Simple cell cropping cuts off feet
  and lets hat edges bleed into the next frame.
AI 生成的图集必然溢出格子，按网格等分硬切会切掉脚/渗进邻帧内容。

流程（agent-sprite-forge split_grid()，steps 不可换）：
 1 网格定位 -> 2 trim_border(4px) -> 3 clean_edges(3层)
 -> 4 连通域(8向) -> 5 touches_edge 溢出校验 -> 6 格内取最大组件
 -> 7 shared_scale(单一因子) -> 8 shared_anchor(防漂移)
"""
import os
import cv2
import numpy as np

import chroma

RAW = "assets_tang/_raw"
OUT = "assets_tang/char"

TRIM_BORDER_PX = 4      # 去掉相邻格共享的抗锯齿接缝
CLEAN_EDGE_DEPTH = 3    # 从边缘向内扫的层数
MIN_AREA = 10           # 噪点阈值（codestudy）
KEY_DIST = 150          # 近键控色判定距离（agent-sprite-forge edge_threshold）
DARK = 40               # 暗色残边判定


def _clean_edges(bgra, depth, key_ref=None):
    """从边缘向内扫 depth 层：擦暗色轮廓残片 + 近键控色溢色。"""
    if depth <= 0:
        return bgra
    out = bgra.copy()
    h, w = out.shape[:2]
    if key_ref is None:
        # 四角取键控色参考（与 chroma_key 一致）
        pts = [out[0, 0, :3], out[0, w - 1, :3], out[h - 1, 0, :3],
               out[h - 1, w - 1, :3]]
        key_ref = np.median(np.array(pts, dtype=np.float64), axis=0)
    key_ref = np.asarray(key_ref, dtype=np.float64)
    for d in range(int(depth)):
        for y in range(d, max(0, h - d)):
            for x in range(d, max(0, w - d)):
                on_band = (y == d or y == h - d - 1 or x == d or x == w - d - 1)
                if not on_band:
                    continue
                if out[y, x, 3] == 0:
                    continue
                b, g, r = out[y, x, :3].astype(np.float64)
                if (r < DARK and g < DARK and b < DARK) or \
                   float(np.linalg.norm(out[y, x, :3].astype(np.float64) - key_ref)) < KEY_DIST:
                    out[y, x, 3] = 0
    return out


def split_grid(bgra, cols, rows, names, anchor_edge="bottom",
               trim_px=TRIM_BORDER_PX, clean_depth=CLEAN_EDGE_DEPTH,
               min_area=MIN_AREA, cell=None, fit=0.92):
    """返回 [{"name":..., "img":BGRA}, ...]，画布统一 + 锚点对齐。"""
    if bgra.ndim == 2 or bgra.shape[2] == 3:
        bgra = cv2.cvtColor(bgra, cv2.COLOR_BGR2BGRA) if bgra.ndim == 2 else \
            np.dstack([bgra, np.full(bgra.shape[:2], 255, np.uint8)])
    H, W = bgra.shape[:2]
    cw, ch = W // cols, H // rows
    if len(names) > cols * rows:
        raise ValueError("names 数 %d 超过网格 %dx%d" % (len(names), cols, rows))

    crops = []
    for i, nm in enumerate(names):
        r, c = divmod(i, cols)
        x0, y0 = c * cw, r * ch
        tile = bgra[y0:min(H, y0 + ch), x0:min(W, x0 + cw)].copy()

        # 2) trim_border
        if trim_px > 0 and min(tile.shape[:2]) > 2 * trim_px + 1:
            tile = tile[trim_px:-trim_px, trim_px:-trim_px]

        # 3) clean_edges
        tile = _clean_edges(tile, clean_depth)

        # 4) 连通域（复用 chroma，逻辑唯一）
        comps = chroma.all_components(tile, min_area=min_area)
        if not comps:
            raise ValueError("格 %d(%s) 无前景组件（min_area=%d）——"
                             "该帧可能未生成或被完全擦除" % (i, nm, min_area))

        # 5) touches_edge 溢出校验
        top = comps[0]
        if top["touches_edge"]:
            raise ValueError(
                "格 %d(%s) 前景触边（bbox=%s）——姿态溢出格子，"
                "硬切会切掉主体或渗入邻帧内容（铁律44）" % (i, nm, top["bbox"]))

        # 6) 格内多组件取最大
        x0_, y0_, x1_, y1_ = top["bbox"]
        crops.append({"name": nm, "img": tile[y0_:y1_, x0_:x1_].copy(),
                      "n_comp": len(comps)})

    # 7) shared_scale：单一因子，防各帧独立缩放放大 bbox 差异
    maxw = max(c["img"].shape[1] for c in crops)
    maxh = max(c["img"].shape[0] for c in crops)
    target = float(cell) if cell else float(max(maxw, maxh))
    shared = (target * fit) / float(max(maxw, maxh))
    for c in crops:
        im = c["img"]
        nw = max(1, int(round(im.shape[1] * shared)))
        nh = max(1, int(round(im.shape[0] * shared)))
        c["img"] = cv2.resize(im, (nw, nh), interpolation=cv2.INTER_AREA)

    # 8) shared_anchor：统一画布 + 锚边对齐，防漂移
    cw2 = max(c["img"].shape[1] for c in crops)
    ch2 = max(c["img"].shape[0] for c in crops)
    for c in crops:
        im = c["img"]
        canvas = np.zeros((ch2, cw2, 4), np.uint8)
        if anchor_edge == "top":
            oy = 0
        else:                     # bottom：脚/底边在同一像素
            oy = ch2 - im.shape[0]
        ox = (cw2 - im.shape[1]) // 2
        canvas[oy:oy + im.shape[0], ox:ox + im.shape[1]] = im
        c["img"] = canvas
    return crops


def self_check():
    ok = True

    def _r(name, cond, note=""):
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + name + ("  " + note if note else ""))
        ok = ok and bool(cond)
        return cond

    def _sheet(cols, rows, boxes, size=(200, 400), pad=30):
        """合成图集：boxes = [(cx0,cy0,cx1,cy1) in cell-local coords]"""
        h, w = size
        im = np.zeros((h, w, 4), np.uint8)
        cwh, chh = w // cols, h // rows
        for i, bx in enumerate(boxes):
            r, c = divmod(i, cols)
            ox, oy = c * cwh, r * chh
            x0, y0, x1, y1 = bx
            im[oy + y0:oy + y1, ox + x0:ox + x1, :3] = 120
            im[oy + y0:oy + y1, ox + x0:ox + x1, 3] = 255
        return im

    # 1) 正常 2x1：两个不触边的方块 -> 切出 2 帧，画布一致
    im = _sheet(2, 1, [(40, 40, 140, 170), (45, 50, 150, 160)])
    r = split_grid(im, 2, 1, ["a", "b"])
    same = len({c["img"].shape for c in r}) == 1
    ok = _r("正常2格切出2帧且画布一致",
            len(r) == 2 and same, "画布=%s" % (r[0]["img"].shape,))

    # 2) 溢出：方块贴到格边 -> 必须报错（证明不是硬切）
    im2 = _sheet(2, 1, [(0, 0, 100, 100), (45, 50, 150, 160)])
    try:
        split_grid(im2, 2, 1, ["a", "b"], trim_px=0, clean_depth=0)
        r2 = False
    except ValueError:
        r2 = True
    _r("触边溢出报错(禁硬切)", r2)

    # 3) 噪点过滤：加一个 3px 小点
    im3 = _sheet(2, 1, [(40, 40, 140, 170), (45, 50, 150, 160)])
    im3[5:8, 5:8, :3] = 120
    im3[5:8, 5:8, 3] = 255
    r3 = split_grid(im3, 2, 1, ["a", "b"])
    _r("噪点被过滤(仍切出2帧)", len(r3) == 2)

    # 4) anchor：bottom 时各帧底边非空像素 y 必须一致（防漂移）
    def _bottom_y(img):
        a = img[:, :, 3]
        ys = np.where(a.max(axis=1) > 0)[0]
        return int(ys.max()) if len(ys) else -1
    im4 = _sheet(2, 1, [(40, 30, 140, 150), (45, 10, 150, 150)])
    r4 = split_grid(im4, 2, 1, ["a", "b"], anchor_edge="bottom")
    ys = [_bottom_y(c["img"]) for c in r4]
    _r("bottom锚点各帧底边对齐", max(ys) - min(ys) <= 1, "底边y=%s" % ys)
    r5 = split_grid(im4, 2, 1, ["a", "b"], anchor_edge="top")
    def _top_y(img):
        a = img[:, :, 3]
        ys = np.where(a.max(axis=1) > 0)[0]
        return int(ys.min()) if len(ys) else -1
    ts = [_top_y(c["img"]) for c in r5]
    _r("top锚点各帧顶边对齐(幡杆用)", max(ts) - min(ts) <= 1, "顶边y=%s" % ts)

    # 5) shared_scale 单一因子：前景高度比必须保持原始比
    # 【证伪】画布统一是第 8 步做的，与 shared_scale 无关；
    # 若改成"各帧独立缩放到同一画布"，前景高比会退化成 1.0 —— 故测前景而非画布
    im6 = _sheet(2, 1, [(40, 20, 140, 100), (40, 20, 140, 180)])   # 80 : 160 = 1:2
    r6 = split_grid(im6, 2, 1, ["a", "b"], cell=128)
    def _fg_h(img):
        ys = np.where(img[:, :, 3].max(axis=1) > 0)[0]
        return int(len(ys))
    h1, h2 = [_fg_h(c["img"]) for c in r6]
    ratio = h1 / float(max(h2, 1))
    _r("shared_scale保相对大小(前景高比≈0.5,独立缩放会变1.0)",
       0.40 <= ratio <= 0.60 and len({c["img"].shape for c in r6}) == 1,
       "前景高=%d:%d 比=%.3f" % (h1, h2, ratio))

    print("\n6 项 -> %s" % ("PASS" if ok else "FAIL"))
    return ok


PLAN = [
    ("xz_sheet.jpg",      4, 2, ["xz_front", "xz_34", "xz_side", "xz_back",
                                 "prop_waterskin", "prop_warrant",
                                 "prop_bundle", "prop_staff"]),
    ("support_sheet.jpg", 4, 1, ["li_daliang", "li_chang", "shi_pantuo",
                                 "old_man"]),
    ("expr_sheet.jpg",    6, 1, ["xz_expr_01", "xz_expr_02", "xz_expr_03",
                                 "xz_expr_04", "xz_expr_05", "xz_expr_06"]),
    ("walk_sheet.jpg",    4, 1, ["xz_walk_01", "xz_walk_02", "xz_walk_03",
                                 "xz_walk_04"]),
]


if __name__ == "__main__":
    import sys
    if "--check" in sys.argv or len(sys.argv) == 1:
        raise SystemExit(0 if self_check() else 1)
    os.makedirs(OUT, exist_ok=True)
    for src, cols, rows, names in PLAN:
        p = os.path.join(RAW, src)
        im = cv2.imread(p, cv2.IMREAD_UNCHANGED)
        if im is None:
            print("跳过（不存在）", src)
            continue
        try:
            for c in split_grid(im, cols, rows, names):
                cv2.imwrite(os.path.join(OUT, c["name"] + ".png"), c["img"])
                print("  %s.png  %dx%d" % (c["name"], c["img"].shape[1],
                                           c["img"].shape[0]))
        except ValueError as e:
            print("FAIL %s: %s" % (src, e))
    print("切分完成")
