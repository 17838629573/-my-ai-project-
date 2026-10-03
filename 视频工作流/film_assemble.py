#!/usr/bin/env python3
"""
镜头装配层 —— 模型填 3 个字段，代码完成全部映射
==================================================
【分工（对应用户要求）】
  模型只填：shot_type / angle / movement 三个【摄影行业枚举】
  代码负责：选资产、定比例、算落点、合成、字幕、编码

  代码不"计算"人物的美术形态 —— 那由生成的图决定。
  代码只做【映射】：把已成型的资产按摄影规则摆进画面。

【两条映射路径】
  native 路径（细节资产 cowboy/medium/mcu）：
    生成时已按"膝盖以上/腰部以上/胸部以上"取景，
    代码整帧缩放到画布，不裁剪、不改构图 —— 保留烘焙好的取景。
  scaled 路径（全身资产 walk/stand/kneel）：
    裁包围盒 -> 按景别反算的人物高度缩放 -> 脚底落在 ground_y。

【为什么这样分】
  用全身图硬裁成中景 = 代码在"算"美术，必然失真。
  正确做法是让生成模型直接出对应景别的图，代码只摆放。
"""
import json
import os
import subprocess
import sys
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cv2
import numpy as np
from character_sheet import CHAR_DIR, SHEET
from chroma import contact_shadow, flood_key, overlay
from photo_rules import BODY, SHOT_TYPES, validate_sequence
from photo_rules import body_pixels, ground_y
from subtitle import draw_subtitle, subtitle_alpha
BASE = os.path.dirname(os.path.abspath(__file__))
BG_DIR = os.path.join(BASE, 'assets_tang', 'bg')

def sub_shift(img, dx, dy=0.0):
    (h, w) = img.shape[:2]
    M = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))

def scroll_bg(bg, dx, W, H):
    sh = cv2.resize(bg, (W, H), interpolation=cv2.INTER_AREA)
    M = np.float32([[1, 0, -dx], [0, 1, 0]])
    return cv2.warpAffine(sh, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)

def prep_native(key, W, H):
    """细节资产：整帧缩放到画布，保留生成时的取景"""
    v = SHEET[key]
    im = cv2.imread(os.path.join(CHAR_DIR, v['file']))
    (bgra, a) = flood_key(im)
    return cv2.resize(bgra, (W, H), interpolation=cv2.INTER_AREA)

def prep_scaled(key, char_h):
    """全身资产：裁包围盒 -> 按景别人物高度缩放 -> 返回 BGRA 与宽高"""
    v = SHEET[key]
    im = cv2.imread(os.path.join(CHAR_DIR, v['file']))
    (bgra, a) = flood_key(im)
    (ys, xs) = np.where(a > 0.5)
    if len(ys) == 0:
        raise RuntimeError(f'{key} 抠像失败')
    (y0, y1, x0, x1) = (ys.min(), ys.max() + 1, xs.min(), xs.max() + 1)
    crop = bgra[y0:y1, x0:x1]
    (h, w) = crop.shape[:2]
    nw = max(1, int(round(w * char_h / h)))
    return cv2.resize(crop, (nw, char_h), interpolation=cv2.INTER_AREA)
NOSEROOM = {'EWS': 0.0, 'WS': 0.1, 'FS': 0.15, 'MFS': 0.25, 'MS': 0.3, 'MCU': 0.3, 'CU': 0.17, 'ECU': 0.1}

def nose_offset_x(st, W, char_w, look='right'):
    """
    返回人物左上角 x。look=视线/运动方向（left/right）。
    人物被推向反方向，为视线前方留出空间。
    """
    nr = NOSEROOM.get(st, 0.0)
    if nr == 0.0:
        return int((W - char_w) / 2)
    if look == 'right':
        return int(W * (0.5 - nr) - char_w / 2)
    return int(W * (0.5 + nr) - char_w / 2)

def resolve_shot(st, H, W, look='right'):
    """由景别反算：人物像素高 + 脚底 y + 构图 x（脚可能出画）"""
    t = SHOT_TYPES[st]
    (char_px, in_frame) = body_pixels(t, H)
    foot = ground_y(t, H, char_px)
    char_w = int(char_px * 0.42)
    x = nose_offset_x(st, W, char_w, look)
    return {'char_px': char_px, 'foot_y': foot, 'in_frame': in_frame, 'char_w': char_w, 'x': x}

def plan_resolve(shots, W, H):
    """把 3 字段声明 -> 完整装配参数"""
    out = []
    for s in shots:
        st = s['shot_type']
        (asset, mode) = _pick_asset(st, s.get('state', 'stand'))
        f = resolve_shot(st, H, W)
        if mode == 'native':
            out.append(dict(name=s['name'], bg=s['bg'], shot_type=st, angle=s.get('angle', 'eye'), movement=s.get('movement', 'static'), caption=s.get('caption', ''), seconds=s.get('seconds', 4.0), asset=asset, mode='native', char_h=H, ground_y=H, x=0))
        else:
            out.append(dict(name=s['name'], bg=s['bg'], shot_type=st, angle=s.get('angle', 'eye'), movement=s.get('movement', 'static'), caption=s.get('caption', ''), seconds=s.get('seconds', 4.0), asset=asset, mode='scaled', char_h=f['char_px'], ground_y=f['foot_y'], x=f['x']))
    return out
META = {'walk_a': dict(poses=['walk'], status='ok'), 'walk_b': dict(poses=['walk'], status='ok'), 'stand': dict(poses=['stand'], status='ok'), 'kneel': dict(poses=['kneel'], status='ok'), 'cowboy': dict(poses=['walk'], status='ok'), 'medium': dict(poses=['stand'], status='ok'), 'mcu': dict(poses=['stand'], status='ok'), 'cu': dict(poses=['stand'], status='broken'), 'hands': dict(poses=['kneel'], status='broken')}

def _pick_asset(shot_type, state):
    """优先 native（细节资产已烘焙取景），其次 scaled"""
    for want in ('native', 'scaled'):
        for (k, v) in SHEET.items():
            m = META.get(k, {})
            if m.get('status') == 'broken':
                continue
            if shot_type in v.get('shots', []) and v['mode'] == want and (state in m.get('poses', [])):
                return (k, want)
    return ('stand', 'scaled')

def overlay_full(dst, bgra, scale=1.0):
    """细节资产整帧贴合（含相机缩放）"""
    (h, w) = bgra.shape[:2]
    if abs(scale - 1.0) > 0.0001:
        (nh, nw) = (int(h * scale), int(w * scale))
        bgra = cv2.resize(bgra, (nw, nh), interpolation=cv2.INTER_AREA)
        (h, w) = (nh, nw)
    (H, W) = dst.shape[:2]
    (y0, x0) = ((H - h) // 2, (W - w) // 2)
    (x0, y0) = (max(0, x0), max(0, y0))
    (x1, y1) = (min(W, x0 + w), min(H, y0 + h))
    src = bgra[:y1 - y0, :x1 - x0]
    a = src[:, :, 3:4].astype(np.uint16)
    roi = dst[y0:y1, x0:x1].astype(np.uint16)
    dst[y0:y1, x0:x1] = ((src[:, :, :3].astype(np.uint16) * a + roi * (255 - a)) // 255).astype(np.uint8)
    return dst
if __name__ == '__main__':
    import sys
    (_ok, _) = self_check()
    sys.exit(0 if _ok else 1)

def self_check(*a, **k):
    from film_assemble_render import self_check as _f
    return _f(*a, **k)

def render_one(*a, **k):
    from film_assemble_render import render_one as _f
    return _f(*a, **k)

