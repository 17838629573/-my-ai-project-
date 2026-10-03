import numpy as np
from PIL import Image, ImageFilter

try:
    import cv2
    HAS_CV2 = True
except Exception:
    HAS_CV2 = False


def build_plate(fg, border=8):
    e = np.concatenate([fg[:border, :].reshape(-1, 3), fg[-border:, :].reshape(-1, 3),
                        fg[:, :border].reshape(-1, 3), fg[:, -border:].reshape(-1, 3)])
    c = np.median(e, axis=0)
    return np.full_like(fg, c), c


def difference_matte(fg, plate, softness=40.0):
    d = np.linalg.norm(fg.astype("float32") - plate.astype("float32"), axis=2)
    return np.clip(d / softness, 0.0, 1.0)


def _erode(a, k=7):
    if HAS_CV2:
        return cv2.erode(a, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    return np.asarray(Image.fromarray((a * 255).astype("uint8")).filter(
        ImageFilter.MinFilter(k))).astype("float32") / 255.0


def _blur(a, r=9):
    if HAS_CV2:
        return cv2.GaussianBlur(a, (r, r), 0)
    return np.asarray(Image.fromarray((a * 255).astype("uint8")).filter(
        ImageFilter.GaussianBlur(r / 2))).astype("float32") / 255.0


def contact_shadow(alpha, dx=0, dy=8, blur=9, strength=0.55):
    core = _erode(alpha)
    sh = np.zeros_like(core)
    sh[dy:, :] = core[:-dy, :]
    if dx:
        sh = np.roll(sh, dx, axis=1)
    return np.clip(_blur(sh, blur) * strength, 0, 1)


def _srgb_to_lin(c):
    """sRGB(0-255) -> linear light(0-1)。合成必须在线性光空间做，
    直接在 sRGB 编码值上加权平均会偏暗（W3C Compositing / Porter-Duff）"""
    x = np.asarray(c, dtype="float32") / 255.0
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def _lin_to_srgb(x):
    """linear light(0-1) -> sRGB(0-255)"""
    x = np.clip(x, 0.0, 1.0)
    s = np.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055)
    return np.clip(s * 255.0 + 0.5, 0, 255).astype("uint8")


def porter_duff_over(dst, src, a):
    """Porter-Duff source-over，线性光 + 预乘 alpha。
    顺序：sRGB解码 -> 预乘 -> Over -> 回 sRGB。禁止在编码域直接插值。"""
    a = a[..., None].astype("float32")
    d = _srgb_to_lin(dst)
    s = _srgb_to_lin(src)
    out_lin = s * a + d * (1.0 - a)      # a 已预乘到 src
    return _lin_to_srgb(out_lin)


def composite_layers(bg, layers):
    out = bg.copy().astype("uint8")
    H, W = out.shape[:2]
    for L in sorted(layers, key=lambda z: z.get("depth", 0)):
        fg, a, x, y = L["rgb"], L["alpha"], L["pos"][0], L["pos"][1]
        h, w = a.shape
        x0, x1 = max(0, x), min(W, x + w)
        y0, y1 = max(0, y), min(H, y + h)
        if x0 >= x1 or y0 >= y1:
            continue
        fx0, fy0 = x0 - x, y0 - y
        fx1, fy1 = fx0 + (x1 - x0), fy0 + (y1 - y0)
        reg = out[y0:y1, x0:x1].astype("float32")
        aa = a[fy0:fy1, fx0:fx1]
        if L.get("contact"):
            sh = contact_shadow(aa, dy=L.get("shadow_dy", 8))
            reg = _lin_to_srgb(_srgb_to_lin(reg) * (1.0 - sh[..., None] * 0.5))
        out[y0:y1, x0:x1] = porter_duff_over(reg, fg[fy0:fy1, fx0:fx1], aa)
    return out


def self_check():
    ok, bad = [], []

    def add(n, c, m=""):
        (ok if c else bad).append(n + (" " + m if m else ""))

    bg = np.full((8, 8, 3), 100, np.uint8)
    A = np.full((8, 8, 3), 200, np.uint8)
    B = np.full((8, 8, 3), 50, np.uint8)
    a6 = np.full((8, 8), 0.6, np.float32)
    r1 = porter_duff_over(porter_duff_over(bg, A, a6), B, a6)
    r2 = porter_duff_over(porter_duff_over(bg, B, a6), A, a6)
    md = int(np.abs(r1.astype(int) - r2.astype(int)).max())
    add("1 Over非交换(顺序敏感)", md > 1, "maxdiff=%d" % md)

    o1 = porter_duff_over(bg, A, np.ones((8, 8), np.float32))
    add("2 alpha=1完全替换", np.abs(o1.astype(int) - 200).max() <= 1)
    o0 = porter_duff_over(bg, A, np.zeros((8, 8), np.float32))
    add("3 alpha=0保留背景", np.abs(o0.astype(int) - 100).max() <= 1)

    import os
    fp = "_旗帧/f/banner_f00.png"
    if os.path.exists(fp):
        fg = np.asarray(Image.open(fp).convert("RGB"))
        plate, col = build_plate(fg)
        a = difference_matte(fg, plate)
        cov = float((a > 0.5).mean())
        add("4 matte非空", cov > 0.005, "前景占比=%.2f%%" % (cov * 100))
        edge = float(((a > 0.05) & (a < 0.95)).mean())
        add("5 半透明边缘(非硬边)", edge > 0, "edge=%.3f%%" % (edge * 100))
        sh = contact_shadow(a)
        add("6 接触阴影非空", sh.max() > 0, "max=%.3f" % float(sh.max()))

        try:
            bgim = np.asarray(Image.open("assets_tang/bg/gate.jpg").convert("RGB").resize((540, 960)))
        except FileNotFoundError:
            # 素材已清空时降级为合成背景：自检只验算法，不验素材是否存在
            bgim = np.zeros((960, 540, 3), np.uint8)
            bgim[:] = (60, 40, 30)
            bgim[450:, :] = (94, 75, 56)
            print("    ⚠ 缺 assets_tang/bg/gate.jpg —— 自检改用合成背景（仅验算法）")
        out = composite_layers(bgim, [
            dict(rgb=fg, alpha=a, pos=(60, 140), depth=1, contact=True),
            dict(rgb=fg, alpha=a, pos=(300, 140), depth=2, contact=True)])
        diff = float(np.abs(out.astype(int) - bgim.astype(int)).mean())
        add("7 真实合成落位", diff > 0.5, "meandiff=%.2f" % diff)
        Image.fromarray(out).save("_证据_合成测试.png")
        print("  输出: _证据_合成测试.png  背板色=%s 旗帧尺寸=%s" % (col.round(0), fg.shape[:2][::-1]))
    else:
        add("4-7 真实资产", False, "asset missing")

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


if __name__ == "__main__":
    import sys
    sys.exit(0 if self_check() else 1)
