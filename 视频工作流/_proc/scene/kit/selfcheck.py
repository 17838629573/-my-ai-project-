# 契约: proc/scene/kit/selfcheck
#   一句话: 自检：python -m kit.selfcheck
#   完整契约见 scene/kit/__init__.py

import os as _os, sys as _sys
if __package__ in (None, ""):
    _d = _os.path.dirname(_os.path.abspath(__file__))
    while _d != _os.path.dirname(_d) and _os.path.basename(_d) != "_proc":
        _d = _os.path.dirname(_d)
    for _p in (_os.path.dirname(_d), _d):
        if _p not in _sys.path:
            _sys.path.insert(0, _p)
    __package__ = _os.path.relpath(
        _os.path.dirname(_os.path.abspath(__file__)), _d).replace(_os.sep, ".")

import math
import numpy as np
from .compose import *
from .canvas import *
from .sky import *
from .terrain import *
from .tree import *
from .city import *
from .road import *
from PIL import Image, ImageDraw

def _chk_scene():
    """场景组合：尺寸对、层序远→近、雾色由天空统一设定。"""
    ok = True
    im, g = compose(SCENES["山区里的城市"], w=270, h=480)
    ok &= (im.size == (270, 480))
    print("  山区里的城市  :", im.size, "层序", g["elements"])

    # 层序正确：mountain 在 city 之前（远→近）
    e = g["elements"]
    order_ok = e.index("mountain") < e.index("city")
    print("  远山先于近城  :", order_ok); ok &= order_ok

    # 雾色被天空设定（所有元件共用）
    fog_ok = g["fog_rgb"] != (150, 160, 170)
    print("  雾色由sky设定 :", fog_ok, g["fog_rgb"]); ok &= fog_ok
    return ok


def _chk_determinism():
    """同场景两次渲染像素级一致（随机性必须固定种子）。"""
    a1, _ = compose(SCENES["山野"], w=180, h=320)
    a2, _ = compose(SCENES["山野"], w=180, h=320)
    det = np.array_equal(np.asarray(a1), np.asarray(a2))
    print("  同场景确定性  :", det)
    return det


def _chk_cloud():
    """云公式：coverage 越大云越多。"""
    def cloud_frac(cov):
        n = fbm2(120, 80, octaves=4, freq=5.0, seed=1.0)
        lo = 0.62 - cov * 0.35
        return float((smoothstep(lo, lo + 0.18, n) > 0.5).mean())
    f1, f2 = cloud_frac(0.2), cloud_frac(0.6)
    mono = f2 > f1
    print("  云量随coverage:", mono, round(f1, 3), "→", round(f2, 3))
    return mono


def _chk_tree():
    """树公式：三种分叉角给出不同剪影（分叉角生效）。"""
    shapes = {}
    for k in ("松", "槐", "橡"):
        cv = Canvas(120, 200, (255, 255, 255))
        ctx = dict(w=120, h=200, horizon_y=100, vanish_x=60,
                   fog_rgb=(150, 160, 170), depth_t=1.0, biome=BIOME_A,
                   rng=np.random.RandomState(0))
        draw_tree(cv, ctx, x=60, ybase=180, height=90, kind=k, jitter=0.0, seed=1)
        a = np.asarray(cv.img.convert("L"))
        shapes[k] = int((a < 200).sum())
    diff_ok = len(set(shapes.values())) >= 2
    print("  树种剪影有别  :", diff_ok, shapes)
    return diff_ok


def _chk_stub():
    """未知元件必须报错，不许静默跳过（STUB 原则的前置）。"""
    try:
        compose({"layers": [{"t": "火山"}]}, w=60, h=100)
        print("  未知元件报错  : False")
        return False
    except KeyError:
        print("  未知元件报错  : True")
        return True


def self_check():
    """逐组自检：断言分组，多失败一起报，不停在第一个。"""
    ok = True
    print("  元件清单:", list_elements())
    for chk in (_chk_scene, _chk_determinism, _chk_cloud, _chk_tree, _chk_stub):
        ok &= bool(chk())
    print("SELF_CHECK:", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    self_check()
