# 契约: proc/motion/character/chain_draw
#   一句话: 布料链绘制：把 Verlet 链的质点画成有宽度的布料多边形
#   完整契约见 motion/character/__init__.py

import numpy as np


def _draw_chains(cv, chains, color, width, height_px=None):
    """把链画成**有宽度的布料**，不是细线。

    之前只画 width 递减的多段线 → 屏幕上就是两根细长条，看着像尾巴。
    布料必须有横向铺开：沿链求法向，左右各偏半个"半宽"，连成闭合多边形。
    """
    dr = cv.d
    L = float(height_px or width * 40.0)
    for name, ch in chains.items():
        p = np.asarray(ch.p, dtype=np.float64)
        n = len(p)
        # 半宽：衣摆是下摆散开的裙（下宽上窄），飘带是窄带（梢更窄）
        if name == "hem":
            hw = L * np.linspace(0.075, 0.115, n)
        else:
            hw = L * np.linspace(0.016, 0.006, n)
        tan = np.vstack([p[1:] - p[:-1], p[-1] - p[-2]])
        ln = np.linalg.norm(tan, axis=1) + 1e-9
        nrm = np.stack([-tan[:, 1] / ln, tan[:, 0] / ln], axis=1)
        left = p + nrm * hw[:, None]
        right = p - nrm * hw[:, None]
        poly = np.vstack([left, right[::-1]])
        dr.polygon([tuple(v) for v in poly], fill=color)
        # 下摆/带梢压一道暗边，布料才有厚度
        dr.line([tuple(v) for v in right], fill=tuple(int(c * 0.72) for c in color),
                width=max(1, int(L * 0.006)))

__all__ = [n for n in dir() if not n.startswith("_")]
