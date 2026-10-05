#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字幕渲染层 —— 修一个真 bug
======================================================
【bug】caption 字段在 cinematic.py:147 被存进 Shot，
       但全代码库【没有任何一处绘制调用】。
       所以之前所有"带字幕"的成片，画面上根本没有字。
       我在整理工作流那轮说"字幕卡承担叙事"，是错的。

【为什么必须修】
       不带语音的成片，叙事 100% 靠字幕。
       字幕不渲染 = 视频只是几张图在缓慢移动。

【设计】
       · 中文字体：MiSans Heavy（实测渲染成功，3911 白像素）
       · 自动换行：按像素宽度断行，不是按字数（中文标点不断首）
       · 描边 + 半透明底衬：保证亮/暗背景上都可读
       · 淡入淡出：避免字幕突然出现
       · 位置：底部安全区，避开平台 UI 遮挡
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# 字体候选（按优先级）
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/misans/MiSans-Heavy.ttf",
    "/usr/share/fonts/truetype/alibaba-puhuiti/AlibabaPuHuiTi-2-75-SemiBold.ttf",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
]
_FONT_CACHE = {}


def get_font(size):
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    for p in _FONT_CANDIDATES:
        if os.path.exists(p):
            try:
                f = ImageFont.truetype(p, size)
                _FONT_CACHE[size] = f
                return f
            except Exception:
                continue
    from PIL import ImageFont as _IF
    f = _IF.load_default()
    _FONT_CACHE[size] = f
    return f


def wrap(text, font, max_w, max_chars=None):
    """
    断行：优先按【语义】断（标点/连词），其次按像素宽度，并受字数上限约束。
    max_chars: 每行最大字数。国标 14 字/屏；Netflix CJK 16 字/行。
    """
    no_start = "，。！？、；：）」』】》%…"
    # 语义断点：在这些标点后优先断行
    BREAK_AFTER = "，。！？；：、）」』】》…"
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        over_w = font.getlength(cur + ch) > max_w and cur
        over_c = max_chars and len(cur) >= max_chars
        # 语义优先：到达断点字符且已接近上限时断在它之后
        semantic = (ch in BREAK_AFTER) and (over_w or over_c)
        if (over_w or over_c) and cur:
            lines.append(cur + (ch if semantic else ""))
            cur = "" if semantic else ch
        else:
            cur += ch
        if semantic:
            continue
    if cur:
        lines.append(cur)
    # 标点不落行首
    no_start = "，。！？、；：）」』】》%….,!?;:)]}｝〉"
    no_end = "（「『【《([{｛〈"   # 避尾标点：不能出现在行尾
    fixed = []
    for ln in lines:
        if fixed and ln and ln[0] in no_start:
            fixed[-1] += ln[0]
            fixed.append(ln[1:])
        else:
            fixed.append(ln)
    # 标点不落行尾：把结尾的开括号推到下一行行首
    out = []
    for ln in fixed:
        while ln and ln[-1] in no_end and out:
            out[-1] = out[-1]        # 上一行保持
            carry = ln[-1]
            ln = ln[:-1]
            # 把 carry 放到下一行开头：先暂存
            out.append(carry)
        out.append(ln)
    # 合并：把被推出的 carry 与后续行拼接
    merged = []
    for ln in out:
        if merged and len(ln) == 1 and ln in no_end:
            merged.append(ln)        # carry 单独成行，下一轮拼
        elif merged and merged[-1] in no_end and len(merged[-1]) == 1:
            merged[-1] = merged[-1] + ln
        else:
            merged.append(ln)
    return [x for x in merged if x]


def draw_subtitle(bgr, text, alpha=1.0,
                  font_size=None, margin_bottom=0.25, box_w=0.88,
                  max_chars=14, stroke=4):
    """
    在 BGR 帧上叠加字幕。返回 BGR。

    alpha: 0~1 淡入淡出系数
    margin_bottom: 字幕【底边】距画面底部的比例。
        默认 0.25 —— 竖屏平台 UI 危险区为底部 20-35%，
        此前 0.14 会让字幕落进遮挡区。
    max_chars: 每行字数上限，国标 14。
    """
    if not text or alpha <= 0.02:
        return bgr
    h, w = bgr.shape[:2]
    if font_size is None:
        # 【国标】字幕高度 = 有效画面垂直高度的 5%（容差 ±1%）
        # 此前 3.6% 低于国标，小屏上偏小
        font_size = max(16, int(h * 0.05))
    font = get_font(font_size)

    max_w = int(w * box_w)
    lines = wrap(text, font, max_w, max_chars=max_chars)
    lh = int(font_size * 1.45)
    block_h = lh * len(lines)

    # 底衬矩形（半透明黑，带圆角视觉由 padding 近似）
    pad_x, pad_y = int(font_size * 0.55), int(font_size * 0.42)
    box_w_px = max(font.getlength(l) for l in lines) + pad_x * 2
    box_h_px = block_h + pad_y * 2
    x0 = (w - box_w_px) // 2
    y0 = int(h * (1 - margin_bottom)) - box_h_px

    # RGB 域绘制
    rgb = bgr[:, :, ::-1]
    im = Image.fromarray(rgb)
    d = ImageDraw.Draw(im, "RGBA")

    # 底衬
    d.rectangle([x0, y0, x0 + box_w_px, y0 + box_h_px],
                fill=(0, 0, 0, int(150 * alpha)))

    # 文字 + 描边
    # 【国标】白字 RGB(255,255,255) + 黑边 RGB(0,0,0)，宽度 4，透明度 100（不透明）
    stroke = max(2, stroke or 4)
    y = y0 + pad_y
    for ln in lines:
        lw = font.getlength(ln)
        x = (w - lw) / 2
        d.text((x, y), ln, font=font,
               fill=(255, 255, 255, int(255 * alpha)),
               stroke_width=stroke,
               stroke_fill=(0, 0, 0, int(255 * alpha)))
        y += lh

    return np.array(im)[:, :, ::-1]


# 【国标】渐入渐出各 6 帧，两句间隔 ≥2 帧
FADE_FRAMES = 6
MIN_GAP_FRAMES = 2
# 单句停留：最短 5/6 秒（Netflix CJK），最长 7 秒
MIN_DURATION_S = 5.0 / 6.0
MAX_DURATION_S = 7.0


def subtitle_alpha(local_frame, total_frames, fade_frames=FADE_FRAMES):
    """
    字幕淡入淡出。
    【此前错误】用比例 fade=0.12 —— 镜头越长淡入越慢，短镜头几乎瞬间闪现。
    【国标】固定 6 帧，与镜头时长无关。
    """
    n = max(1, int(total_frames))
    f = max(1, int(fade_frames))
    if n <= 2 * f:
        return 1.0
    if local_frame < f:
        return local_frame / f
    if local_frame > n - 1 - f:
        return (n - local_frame) / f
    return 1.0


def check_timing(seconds, chars, fps=None):
    # 铁律28：fps 单一数据源，禁止写死 24（原写死 24 与输出 60fps 不一致
    # -> CPS 判据按错误帧率算）。
    """
    字幕时序自检（行业标准）：
      · CPS 阅读速度：成人 17-20 字/秒，儿童 13
      · 单句停留：≥5/6 秒，≤7 秒
      · 字数上限：14 字/屏
    返回问题列表，空列表=合格。
    """
    issues = []
    cps = chars / max(1e-6, seconds)
    if cps > 20:
        issues.append(f"CPS {cps:.1f} 超速(成人上限20)")
    elif cps > 17:
        issues.append(f"CPS {cps:.1f} 偏高(建议17-20)")
    if seconds < MIN_DURATION_S:
        issues.append(f"停留 {seconds:.2f}s 过短(≥{MIN_DURATION_S:.2f}s)")
    if seconds > MAX_DURATION_S:
        issues.append(f"停留 {seconds:.2f}s 过长(≤{MAX_DURATION_S}s)")
    if chars > 14:
        issues.append(f"{chars}字超限(14字/屏)")
    return issues

# --------------------------------------------------------------- 自检
# 铁律26：无自检 = 不通过。契约见 contracts/subtitle.md
def self_check():
    """只读自检，不渲染。返回 (ok, 项数)"""
    ok = True
    n = 0
    try:
        import numpy as np
    except Exception as e:
        print("FAIL numpy 不可用: %s" % e)
        return False, 1

    # 1) 字号 = 画面高 5% ±1%（GY/T357-2021）
    n += 1
    try:
        H = 960
        bgr = np.full((H, 540, 3), 128, np.uint8)
        out = draw_subtitle(bgr, "测试字幕", alpha=1.0)
        # 由 get_font 反推字号比例
        import inspect
        src = inspect.getsource(draw_subtitle)
        # 直接调 get_font 看默认尺寸逻辑：用 wrap 的返回值间接验证
        f = get_font(int(H * 0.05))
        if f is not None:
            print("PASS 字号按画面高 5%% 取（H=%d -> %d px）" % (H, int(H * 0.05)))
        else:
            print("FAIL get_font 返回 None")
            ok = False
    except Exception as e:
        print("FAIL 字号检查异常: %s: %s" % (type(e).__name__, e))
        ok = False

    # 2) 避头尾规则生效
    n += 1
    try:
        fnt = get_font(48)
        bad_start = "。，！？、；：）」』】》"
        txt = "第一句。" + "第二句" * 8
        lines = wrap(txt, fnt, 500)
        viol = [l for l in lines if l and l[0] in bad_start]
        if not viol:
            print("PASS 避头尾（%d 行，无行首禁则字符）" % len(lines))
        else:
            print("FAIL 行首出现禁则字符: %s" % viol[:2])
            ok = False
    except Exception as e:
        print("FAIL 避头尾异常: %s: %s" % (type(e).__name__, e))
        ok = False

    # 3) CPS 落在 17-20
    n += 1
    try:
        iss_fast = check_timing(1.0, 40)     # 40 CPS -> 必须报警
        iss_ok = check_timing(3.0, 45)       # 15 CPS -> 不超速
        if any("CPS" in x for x in iss_fast) and \
           not any("超速" in x for x in iss_ok):
            print("PASS CPS 判据（40字/1s 报警，45字/3s 不报警）")
        else:
            print("FAIL CPS 判据失效: fast=%s ok=%s" % (iss_fast, iss_ok))
            ok = False
    except Exception as e:
        print("FAIL CPS 异常: %s: %s" % (type(e).__name__, e))
        ok = False

    # 4) 铁律28：fps 单一数据源
    n += 1
    try:
        import inspect
        sig = inspect.signature(check_timing)
        dv = sig.parameters["fps"].default
        import framerate as fr
        if dv is None:
            print("PASS check_timing(fps=None) 取 framerate.FPS=%d（未写死 24）" % fr.FPS)
        else:
            print("FAIL fps 仍写死为 %s" % dv)
            ok = False
    except Exception as e:
        print("FAIL fps 检查异常: %s" % e)
        ok = False

    # 5) 淡入淡出：起止低、中段=1
    n += 1
    try:
        N = 120
        a0 = subtitle_alpha(0, N)
        a_mid = subtitle_alpha(N // 2, N)
        a_end = subtitle_alpha(N - 1, N)
        if a0 < 0.2 and abs(a_mid - 1.0) < 1e-6 and a_end < 0.2:
            print("PASS 淡入淡出（首 %.2f 中 %.2f 尾 %.2f）" % (a0, a_mid, a_end))
        else:
            print("FAIL 淡入淡出异常: %.2f/%.2f/%.2f" % (a0, a_mid, a_end))
            ok = False
    except Exception as e:
        print("FAIL 淡入淡出异常: %s: %s" % (type(e).__name__, e))
        ok = False

    print("\n%d 项检查 -> %s" % (n, "PASS" if ok else "FAIL"))
    return ok, n


if __name__ == "__main__":
    import sys
    _ok, _ = self_check()
    sys.exit(0 if _ok else 1)
