"""分层合成四要素（铁律101）：投影/环境反光/正片叠底/全局色彩平衡
业界依据：拼贴感来自"前景没吃环境光"。四要素缺一即假。"""
import cv2, numpy as np

def _soft(alpha, k=9, r=11):
    a = alpha.astype(np.float32) / 255.0          # 归一化到 0-1（否则投影不透明度失控）
    if k > 1:
        a = cv2.erode(a, np.ones((k, k), np.uint8))
    return cv2.GaussianBlur(a, (0, 0), r)

def contact_shadow(alpha, dx=0, dy=10, blur=11, strength=0.18):
    """要素1：柔边黑投影，15%-20% 不透明度（业界实测值）"""
    a = _soft(alpha, 9, blur)
    sh = np.zeros_like(a)
    M = np.float32([[1, 0, dx], [0, 1, dy]])
    cv2.warpAffine(a, M, (a.shape[1], a.shape[0]), dst=sh,
                   flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    m = float(sh.max())                        # 归一化：峰值恒等于 strength，不受图幅/模糊半径影响
    if m > 1e-6:
        sh = sh / m
    return np.clip(sh * strength, 0.0, 1.0)    # strength=0.18 落在业界 15%-20%

def env_reflection(fg, alpha, bg_tint, opacity=0.12):
    """要素2：环境反光——背景主色调染到前景，10%-15%，消除拼接感最关键一步"""
    tint = np.asarray(bg_tint, np.float32).reshape(1, 1, 3)
    a = (alpha.astype(np.float32) / 255.0)[..., None]
    # 边缘渐变更吃环境光（内部少、轮廓多）
    edge = np.clip(_soft(alpha, 5, 7) * 1.6, 0, 1)[..., None]
    w = np.clip(edge * opacity, 0, 1)
    out = fg.astype(np.float32) * (1 - w) + tint * w
    return (out * a + fg.astype(np.float32) * (1 - a)).clip(0, 255).astype(np.uint8)

def multiply_shade(dst, shadow):
    """要素3：正片叠底 C = A*B/255（加深接触阴影，非简单变暗）"""
    s = shadow[..., None].astype(np.float32) if shadow.ndim == 2 else shadow.astype(np.float32)
    return (dst.astype(np.float32) * (1.0 - s)).clip(0, 255).astype(np.uint8)

def global_grade(fg, bg):
    """要素4：顶层全局色彩平衡——前景色温/亮度向背景靠拢
    bg 可传图像或预计算的均值向量（性能）"""
    fb = fg.astype(np.float32)
    bb = np.asarray(bg, np.float32)
    if bb.ndim >= 2: bb = bb.reshape(-1, 3).mean(0)
    mf = fb.reshape(-1, 3).mean(0); mb = bb
    gain = np.clip(mb / np.maximum(mf, 1.0), 0.85, 1.18)   # 限制幅度防过冲
    return (fb * gain).clip(0, 255).astype(np.uint8)

def bg_tint_of(bg, alpha=None):
    """取背景主色调（忽略极暗/极亮像素）"""
    px = bg.reshape(-1, 3).astype(np.float32)
    lum = px.mean(1)
    keep = px[(lum > 30) & (lum < 240)]
    return keep.mean(0) if len(keep) else px.mean(0)

def over(dst, src, a):
    """Porter-Duff Over"""
    a3 = a[..., None].astype(np.float32)
    return (src.astype(np.float32) * a3 + dst.astype(np.float32) * (1 - a3)).clip(0, 255).astype(np.uint8)
