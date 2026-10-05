[S] physics @ATOM/phys  d1  in=13  gen:contract_gen
does: physics.py —— 物理原子层（逻辑唯一实现，数值全外置）
api: volume, area, force, force_per_area, accel, torque, px_per_m, beaufort, beaufort_level, rel_wind, swing_angle, swing_offset (+5)
const: RHO_AIR, G, RHO_BODY, K_SHAPE, K_SHAPE_DEFAULT, BEAUFORT, V_REF, BEAUFORT_DESC (+2)
impl: 入口 volume
up: _common,_px
down: _chk_base,_chk_motion,_solver_chain,actors,environment,render_desert_banner (+7)
edit: _chk_base,_chk_motion,_common,_px,_solver_chain,actors,environment,render_desert_banner,render_gate_banner,render_v4,render_v4_main,systems,systems_phys,systems_selfcheck,systems_view   # 改physics须同步核对这些文件
rule: T18 T86 T88
why : IMPROVE_physics.md
