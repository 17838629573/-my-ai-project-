"""chroma 的自检/检查逻辑（由 _extract_tool.py 从 chroma.py 抽出）

改前必读: IMPROVE_chroma.md
"""
import os
import cv2
import numpy as np
from chroma import chroma_key, flood_key, overlay, trim_alpha

def self_check():
    """用【合成图】自检，不依赖资产目录。返回 (ok, 项数)"""
    ok = True
    n = 0
    try:
        import numpy as np
    except Exception as e:
        print("FAIL numpy 不可用: %s" % e)
        return False, 1

    def _first(x):
        """各函数返回 (bgra, meta) 或 bgra —— 统一取 bgra"""
        return x[0] if isinstance(x, tuple) else x

    def _synthetic():
        """纯白底 + 中间一块深色矩形（模拟角色/物件）"""
        img = np.full((200, 120, 3), 255, np.uint8)
        img[50:150, 40:80] = (60, 40, 30)      # BGR 深色块
        return img

    # 1) chroma_key 分离前景/背景
    n += 1
    try:
        bgra = _first(chroma_key(_synthetic()))          # 实际返回 (bgra, alpha)
        if bgra.shape[2] != 4:
            print("FAIL chroma_key 未返回 BGRA")
            ok = False
        else:
            a = bgra[:, :, 3]
            fg = float((a > 127).mean())
            if 0.05 < fg < 0.60:
                print("PASS chroma_key 分离成功（前景占比 %.1f%%）" % (fg * 100))
            else:
                print("FAIL 前景占比异常 %.1f%%" % (fg * 100))
                ok = False
    except Exception as e:
        print("FAIL chroma_key 异常: %s: %s" % (type(e).__name__, e))
        ok = False

    # 2) flood_key alpha 是 0-1 float（阈值 0.5 不是 128）
    n += 1
    try:
        r = flood_key(_synthetic())
        # r 可能是 (bgra, alpha) 或 bgra；取 alpha 判断
        alpha = r[1] if isinstance(r, tuple) else r[:, :, 3]
        if alpha.dtype.kind == "f" and float(alpha.max()) <= 1.0 + 1e-6:
            print("PASS flood_key alpha 为 0-1 float（max=%.3f，阈值须用 0.5）"
                  % float(alpha.max()))
        else:
            print("FAIL alpha dtype=%s max=%s（应为 float 且 max<=1）"
                  % (alpha.dtype, alpha.max()))
            ok = False
    except Exception as e:
        print("FAIL flood_key 异常: %s: %s" % (type(e).__name__, e))
        ok = False

    # 3) trim_alpha 裁到包围盒且 pad 生效
    n += 1
    try:
        bgra = _first(chroma_key(_synthetic()))
        t0 = _first(trim_alpha(bgra, pad=0))
        t1 = _first(trim_alpha(bgra, pad=10))
        if t1.shape[0] >= t0.shape[0] and t1.shape[1] >= t0.shape[1]:
            print("PASS trim_alpha pad 生效（%dx%d -> %dx%d）"
                  % (t0.shape[1], t0.shape[0], t1.shape[1], t1.shape[0]))
        else:
            print("FAIL pad 无效")
            ok = False
    except Exception as e:
        print("FAIL trim_alpha 异常: %s: %s" % (type(e).__name__, e))
        ok = False

    # 4) overlay 不越界
    n += 1
    try:
        dst = np.full((300, 300, 3), 128, np.uint8)
        bgra = _first(chroma_key(_synthetic()))
        before = dst.copy()
        overlay(dst, bgra, 500, 500)          # 故意越界
        if dst.shape == before.shape:
            print("PASS overlay 越界不崩且尺寸不变")
        else:
            print("FAIL overlay 尺寸变了")
            ok = False
    except Exception as e:
        print("FAIL overlay 越界异常: %s: %s" % (type(e).__name__, e))
        ok = False

    # 5) 铁律15：形状合理性
    #    ⚠ 已知局限（实测）：纯几何拦不住历史那个 bug ——
    #      问题资产宽高比 0.264，落在 0.05~20 区间内，本检查会判 PASS。
    #      真正区分它的是【主色】与【水平方向分离前景块】，而这两者需与
    #      声明物性比对，纯几何做不到。故本项只拦极端异常，形态判断归 AI
    #      （铁律18）。这里同时输出主色供人工/AI 复核。
    n += 1
    try:
        bgra = _first(chroma_key(_synthetic()))
        t = _first(trim_alpha(bgra, pad=0))
        h, w = t.shape[:2]
        a = t[:, :, 3]
        ratio = (w / h) if h else 0.0
        fill = float((a > 127).mean())
        m = a > 127
        dom = t[:, :, :3][m].mean(axis=0) if m.any() else np.zeros(3)
        if not (0.02 <= ratio <= 50.0 and 0.01 <= fill <= 0.99):
            print("FAIL 形状极端异常（宽高比 %.3f，填充率 %.1f%%）" % (ratio, fill * 100))
            ok = False
        else:
            print("PASS 形状在极端阈值内（宽高比 %.2f，填充率 %.1f%%）"
                  % (ratio, fill * 100))
            print("     ⚠ 主色 BGR=[%.0f,%.0f,%.0f] —— 需与声明物性比对，"
                  "本项【不】自动判对错（铁律18：形态归 AI）"
                  % (dom[0], dom[1], dom[2]))
    except Exception as e:
        print("FAIL 形状检查异常: %s: %s" % (type(e).__name__, e))
        ok = False

    print("\n%d 项检查 -> %s" % (n, "PASS" if ok else "FAIL"))
    return ok, n
