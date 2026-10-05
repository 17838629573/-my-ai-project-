[S] _common @ATOM/math  d0  in=8  gen:contract_gen
does: _common.py —— 跨模块原子复用库（单一定义，全局调用）
api: clamp, lerp, smoothstep, catmull_rom, rad2deg, deg2rad, normalize_deg, normalize_rad, pixels_per_meter, meters_to_px, px_to_meters, beaufort_scale (+12)
const: PI, DEG, RAD, HUMAN_PROPORTION, LEG_RATIO, BEAUFORT, FLAG_MOTION, CONTACT_V_MAX (+1)
impl: 入口 clamp
down: _common_selfcheck,build_phase_gen,build_util,physics,physics_rules,puppet (+2)
edit: _common_selfcheck,build_phase_gen,build_util,physics,physics_rules,puppet,rain_layer,wind_response   # 改_common须同步核对这些文件
rule: T89
why : IMPROVE__common.md
