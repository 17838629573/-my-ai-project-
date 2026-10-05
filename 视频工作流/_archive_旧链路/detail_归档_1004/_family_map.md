[FACT] _family_map   104行   机器生成，勿手改
doc: _family_map —— 五类 → 物理形态 唯一映射（铁律88）
api:
  L35 to_physics_dyn(fam,spec)  # 五类 -> 物理形态（含动态规则）。spec 有 links 则走受迫链。
  L47 is_five(fam)  # 是否对外五类之一。
  L52 to_physics(fam)  # 五类 -> 物理形态。非五类直接报错（铁律88：禁静默降级）。
  L61 need_physics(fam)  # 该族是否需要物理振动求解。rigid 不需要。
  L71 self_check()
internal:
  L67 _chk(name,ok,info)
calls_in: to_physics_dyn→to_physics, to_physics→is_five, need_physics→to_physics, self_check→_chk, self_check→need_physics, self_check→to_physics, self_check→to_physics_dyn
calls_out: FAMILY_TO_PHYSICS,ok,spec
guard: return@L38, raise@L54
const: FIVE[5], PHYSICS[6], FAMILY_TO_PHYSICS[5]
main: __main__@L98  self_check@L71
up: -
down: _solver_chain
