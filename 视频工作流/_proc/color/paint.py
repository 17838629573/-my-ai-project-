# 契约: proc/color/paint
#   一句话: 按胶囊 region 查色卡，配合 SDF 法线做明暗着色；颜色挂 region 不挂像素
#   完整契约见 color/__init__.py
"""第二部分：填色。

颜色挂在 region（胶囊标签）上，不挂在像素上 —— 骨架动了颜色自动跟着走。
明暗用 ramp（暗面→基色→高光），配 SDF 法线着色，保住已有的立体感。

色值来源：
  肤色   Fitzpatrick 六型（皮肤科标准，含细分）
  传统色 国风色彩参照（赭石/朱砂/银朱/胭脂/藤黄/石青/花青/石绿）
  ramp   5 级色阶；阴影侧偏冷（环境/天空），高光侧偏暖（阳光）
"""
import numpy as np

# ---------------------------------------------------------------- 肤色
# Fitzpatrick 六型，每型两档（浅/深）
FITZPATRICK = {
    "I":  ["#F6E4D9", "#F2D6C9"],
    "II": ["#EBC1A9", "#E8B49A"],
    "III": ["#CE9A81", "#D1A17D"],
    "IV": ["#B58A6D", "#A17A5D"],
    "V":  ["#8C5B4C", "#78493D"],
    "VI": ["#543830", "#3D2D27"],
}

# ---------------------------------------------------------------- 国风传统色
TRAD = {
    "赭石": "#845A33", "朱砂": "#FF461F", "银朱": "#BF242A",
    "胭脂": "#9D2933", "朱膘": "#F36838", "藤黄": "#FFB61E",
    "雌黄": "#FFC64B", "雄黄": "#E9BB1D", "石绿": "#16A951",
    "石青": "#1685A9", "花青": "#003472", "白粉": "#FFF2DF",
}

# ---------------------------------------------------------------- 色阶 ramp
# 5 级：暗面 → 基色 → 高光。同一材质共用一条 → 画面统一
RAMPS = {
    "skin":  ["#5a3232", "#8a5050", "#b87878", "#d8a070", "#f0c898"],
    "robe":  ["#3a2418", "#6b3f28", "#8c5a33", "#b07d4a", "#d8a86a"],
    "fur":   ["#3a3630", "#6b6258", "#968b7c", "#bdb3a2", "#e4dccb"],
    "stone": ["#2a2638", "#4a4252", "#6c6276", "#8e8896", "#b0b0b0"],
    "wood":  ["#2e1f14", "#54331f", "#7a4a2c", "#a06a40", "#c89a68"],
    "metal": ["#2a2a2a", "#4f4f4f", "#787878", "#a8a8a8", "#d8d8d8"],
    "foliage": ["#1a3a18", "#2e5a2a", "#4a7a3e", "#7a9a52", "#aabd6a"],
    "water": ["#1a2a4a", "#2e4a76", "#5278a8", "#88a8d0", "#b8d8f0"],
    "sole":  ["#241a12", "#4a3524", "#6e503a", "#8f6d52", "#b28f70"],
    "hair":  ["#14100c", "#2e241a", "#4a3a28", "#6b543c", "#8c7154"],
}

# region → ramp 的默认映射（换角色时按物种继承，character 覆盖）
REGION_RAMP = {
    "skin": "skin", "robe": "robe", "fur": "fur", "hair": "hair",
    "sole": "sole", "metal": "metal", "wood": "wood", "stone": "stone",
}


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def ramp(name, n=5):
    """取一条色阶 → RGB 数组 (n,3)，从暗到亮。"""
    rs = RAMPS.get(name)
    if rs is None:
        raise KeyError(f"未知色阶 {name}，可用 {list(RAMPS)}")
    return np.array([hex2rgb(c) for c in rs], dtype=np.float32)


def skin_rgb(fitz="III", idx=0):
    """按 Fitzpatrick 型取肤色 RGB。"""
    return np.array(hex2rgb(FITZPATRICK[fitz][idx]), dtype=np.float32)


# ---------------------------------------------------------------- 着色
def shade(d, ramp_rgb, light=(-0.55, -0.62, 0.56), amb=0.42,
          rim_pow=2.6, rim_amt=0.34, d_max=None):
    """inflate 伪 3D：由 SDF 直接算法线，再把法线亮度映射到 ramp 的哪一级。

    边缘 nz=0（垂直视线）→ 取 ramp 暗端
    中心 nz=1（朝向观察者）→ 取 ramp 亮端
    单色会抹平立体感，所以必须走 ramp。
    """
    inside = d < 0.0
    out = np.zeros((*d.shape, 3), dtype=np.float32)
    if not inside.any():
        return out

    if d_max is None:
        d_max = max(-d[inside].min(), 1e-6)

    gy, gx = np.gradient(d)
    gl = np.sqrt(gx * gx + gy * gy) + 1e-9
    nx, ny = gx / gl, gy / gl

    # 伪 3D 法线的 z 分量（Lumo 式边界条件）
    nz = np.sqrt(np.clip(1.0 - (1.0 - np.clip(-d / d_max, 0, 1)) ** 2, 0, 1))
    # 亮度：SDF 深度 + 法线朝向，两者结合
    lam = np.clip(nx * light[0] + ny * light[1] + nz * light[2], 0, 1)
    lum = np.clip(amb + (1.0 - amb) * lam, 0, 1)

    # 亮度 → ramp 索引（0=暗端, n-1=亮端）
    n = len(ramp_rgb)
    fi = lum * (n - 1)
    i0 = np.clip(np.floor(fi).astype(np.int32), 0, n - 1)
    i1 = np.clip(i0 + 1, 0, n - 1)
    fr = (fi - i0)[..., None]
    col = ramp_rgb[i0] * (1 - fr) + ramp_rgb[i1] * fr

    rim = np.clip(1.0 - nz, 0, 1) ** rim_pow
    out[inside] = col[inside] + (rim_amt * 255.0 * rim[inside])[..., None]
    return np.clip(out, 0, 255)


def paint_regions(d, region_masks, palette, light=None, **kw):
    """按 region 分区着色。

    region_masks: {region名: 布尔蒙版}（由胶囊各自建场得到，跟着骨架走）
    palette:      {region名: ramp名 或 (r,g,b)}
    返回合成后的 (H,W,3)。
    """
    res = np.zeros((*d.shape, 3), dtype=np.float32)
    done = np.zeros(d.shape, dtype=bool)
    kw2 = {} if light is None else {"light": light}
    kw2.update(kw)
    for reg, mask in region_masks.items():
        if mask is None or not np.any(mask):
            continue
        p = palette.get(reg, REGION_RAMP.get(reg, "stone"))
        rr = ramp(p) if isinstance(p, str) else np.array([p] * 5, dtype=np.float32)
        c = shade(np.where(mask, d, 1e6), rr, **kw2)
        m = np.logical_and(mask, ~done)
        res[m] = c[m]
        done |= m
    # 剩余部分用主 region 兜底
    if not done.all():
        m = ~done
        p = palette.get("_default", "robe")
        rr = ramp(p) if isinstance(p, str) else np.array([p] * 5, dtype=np.float32)
        c = shade(np.where(m, d, 1e6), rr, **kw2)
        res[m] = c[m]
    return res
