[S] physics_rules @ATOM/phys  d1  in=5  gen:contract_gen
does: physics_rules.py —— 物性推导与风力计算
api: volume_of, frontal_area, vogel_exponent, drag_force, accel, beaufort, raindrop_v, describe
const: RHO_AIR, G, RHO_TISSUE, K_SHAPE, TRUNK_EXPONENT, B_VOGEL, BEAUFORT
impl: 入口 volume_of
up: _common
down: environment,systems,systems_phys,systems_selfcheck,systems_view
edit: _common,environment,systems,systems_phys,systems_selfcheck,systems_view   # 改physics_rules须同步核对这些文件
rule: T88
why : IMPROVE_physics_rules.md
