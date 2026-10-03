#!/usr/bin/env python3
"""
渲染 v4 —— 按需调度版
==================================================
【与 v3 的根本区别】
  v3: 每个镜头跑同一套代码（骨架/物理/合成/字幕全量执行）
  v4: 镜头声明 tags -> 引擎解析依赖 -> 只启用需要的系统

【模型只填】
  shot_type / angle / movement / state  （摄影行业枚举）
  + has_walk / has_wind  （决定唤醒哪些系统）

【代码负责】
  依赖解析、系统启停、渲染、编码

【镜头 -> 系统映射】
  静态对话      -> 合成 + 字幕              （骨架/物理休眠）
  行走          -> 合成 + 骨架动画 + 字幕
  沙漠有风行走  -> 合成 + 骨架动画 + 物理 + 字幕
"""
import os
import physics as ph
import subprocess
import sys
import time
import cv2
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import actors
import systems
from loop_engine import LoopEngine
from systems import update_movables, Ctx, init_physics, init_skeleton, update_animation, update_composite, update_physics, update_subtitle
from photo_rules import SHOT_TYPES, body_pixels, ground_y, validate_shot, validate_sequence
from film_assemble import nose_offset_x
BASE = os.path.dirname(os.path.abspath(__file__))
BG_DIR = os.path.join(BASE, 'assets_tang', 'bg')
OUT = sys.argv[1] if len(sys.argv) > 1 else '_成片_新.mp4'
import framerate
from framerate import FPS
(W, H) = (540, 960)
ENC_IN = ['-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(FPS), '-fflags', 'nobuffer', '-probesize', '32', '-flags', 'low_delay', '-thread_queue_size', '512', '-i', '-']
ENC_OUT = ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', '-pix_fmt', 'yuv420p']

def make_parts():
    """程序化生成身体部件（赭黄僧袍配色）"""

    def rect(w, h, bgr):
        im = np.zeros((h, w, 4), np.uint8)
        cv2.rectangle(im, (2, 2), (w - 3, h - 3), bgr, -1)
        im[:, :, 3] = 255
        return im

    def ell(w, h, bgr):
        im = np.zeros((h, w, 4), np.uint8)
        cv2.ellipse(im, (w // 2, h // 2), (w // 2 - 2, h // 2 - 2), 0, 0, 360, bgr, -1)
        im[:, :, 3] = 255
        return im
    ROBE = (60, 140, 190)
    SKIN = (150, 190, 225)
    DARK = (40, 95, 130)
    return {'head': ell(54, 58, SKIN), 'torso': rect(78, 150, ROBE), 'legL': rect(32, 170, DARK), 'legR': rect(32, 170, ROBE), 'armL': rect(26, 130, ROBE), 'armR': rect(26, 130, ROBE)}
SHOTS = [dict(name='01_gate', bg='gate', shot_type='FS', angle='eye', movement='static', look='right', caption='朝廷批复只有四个字：有诏不许', seconds=3.0, has_walk=True, has_wind=False, actors=[('xz', 'walk')]), dict(name='02_hall', bg='hall', shot_type='MS', angle='eye', movement='static', look='left', caption='讲经一个月，讲来了都督', seconds=3.0, has_walk=False, has_wind=False, actors=[('xz', 'stand'), ('li_daliang', 'idle')]), dict(name='03_office', bg='office', shot_type='MCU', angle='low', movement='static', look='left', caption='我说：欲西求法。他说：还京', seconds=3.0, has_walk=False, has_wind=False, actors=[('xz', 'stand'), ('li_daliang', 'idle')]), dict(name='04_yamen', bg='yamen', shot_type='MS', angle='eye', movement='static', look='right', caption='他当着我的面，撕了通缉令', seconds=3.0, has_walk=False, has_wind=False, actors=[('xz', 'stand'), ('li_chang', 'idle')]), dict(name='05_river', bg='river', shot_type='FS', angle='eye', movement='static', look='right', caption='向导提着刀，在我面前来回走了三次', seconds=3.0, has_walk=True, has_wind=False, actors=[('xz', 'stand'), ('shi_pantuo', 'walk')]), dict(name='06_desert', bg='desert', shot_type='EWS', angle='high', movement='static', look='right', caption='四夜五天，一滴水都没有', seconds=4.0, has_walk=True, has_wind=True, actors=[('xz', 'walk')], wind_level=6, movables=[('banner', 'sway')]), dict(name='07_oasis', bg='oasis', shot_type='FS', angle='eye', movement='static', look='right', caption='那匹又瘦又老的赤马，它认得路', seconds=3.0, has_walk=False, has_wind=False, actors=[('xz', 'stand'), ('horse', 'idle')]), dict(name='08_yiwu', bg='yiwu', shot_type='MS', angle='low', movement='static', look='right', caption='国境线上写着：禁止出境。我是翻墙出去的', seconds=3.0, has_walk=True, has_wind=False, actors=[('xz', 'walk')])]

def build_engine():
    eng = LoopEngine()
    eng.register('skeleton', init_fn=init_skeleton, update_fn=None)
    eng.register('animation', init_fn=None, update_fn=update_animation, deps=['skeleton'])
    eng.register('movables', init_fn=None, update_fn=update_movables)
    eng.register('physics', init_fn=init_physics, update_fn=update_physics, deps=['skeleton'])
    eng.register('composite', init_fn=None, update_fn=update_composite)
    eng.register('subtitle', init_fn=None, update_fn=update_subtitle)
    eng.bind_tag('has_walk', ['animation'])
    eng.bind_tag('has_wind', ['physics'])
    eng.bind_tag('has_movables', ['movables'])
    eng.set_always(['composite', 'subtitle'])
    return eng

def check_all_shots():
    """渲染前硬校验：分镜声明的动作，代码必须能驱动"""
    errs = list(actors.check_body_type())
    for s_ in SHOTS:
        errs += actors.check_shot(s_['name'], s_.get('actors', []))
    if errs:
        print('[actors 门禁] FAIL')
        for e in errs:
            print('  x', e)
        raise SystemExit('渲染被拒绝：先补实现或改叙事')
    print('[actors 门禁] PASS —— 所有声明的动作均可驱动')

def _load_seq(chdir, base_file):
    """加载 <stem>_f01..fNN.png 序列。返回 list[BGRA] 或 None（无序列）。"""
    import re, glob
    stem = os.path.splitext(base_file)[0]
    fs = sorted(glob.glob(os.path.join(chdir, stem + '_f*.png')), key=lambda p: int(re.search('_f(\\d+)\\.png$', p).group(1)))
    out = []
    for p in fs:
        im = cv2.imread(p, cv2.IMREAD_UNCHANGED)
        if im is None:
            continue
        if im.shape[2] == 3:
            im = cv2.cvtColor(im, cv2.COLOR_BGR2BGRA)
        out.append(im)
    return out if len(out) >= 2 else None
LEGACY_OUT_NAMES = ('大唐偷渡客_v4.mp4', '大唐偷渡客_v5.mp4', '大唐偷渡客_v6.mp4', '大唐偷渡客_v7.mp4')
if __name__ == '__main__':
    if '--render' in sys.argv:
        main()
    else:
        (_ok, _) = self_check()
        sys.exit(0 if _ok else 1)

def self_check(*a, **k):
    from render_v4_main import self_check as _f
    return _f(*a, **k)

def main(*a, **k):
    from render_v4_main import main as _f
    return _f(*a, **k)

