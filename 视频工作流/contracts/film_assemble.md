# film_assemble ·黄 镜头装配
史:notes/film_assemble.md

接口: META, resolve_shot(st,H,W,look)->{char_px,foot_y,in_frame,char_w,x},
      plan_resolve, _pick_asset, render_one, prep_native, prep_scaled,
      overlay_full, scroll_bg, sub_shift, NOSEROOM, nose_offset_x
构图: NOSEROOM EWS0.0｜WS0.10｜FS0.15｜MFS0.25｜MS/MCU0.30｜CU0.17｜ECU0.10
注: 半身景别 char_w 可达画面宽2-7倍，x为负属正常，可见宽度恒>0

**self_check()（铁律26）**
`python3 film_assemble.py` 默认自检，不渲染（ffmpeg 子进程慢且不必要）。检查项：
  1. NOSEROOM 覆盖全部 SHOT_TYPES（缺景别 -> 构图崩）
  2. resolve_shot 对每种景别都能返回可见宽度 > 0
  3. 【铁律28】render_one(fps) 默认取 framerate.FPS，不得写死 60
  4. META 中 status=broken 的资产不得被 _pick_asset 选中
  5. scroll_bg / sub_shift 的位移边界（不越界、不留黑边）
