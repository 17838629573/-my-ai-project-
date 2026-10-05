[S] _family_map @ATOM/rule  d0  in=1  gen:contract_gen
does: _family_map —— 五类 → 物理形态 唯一映射（铁律88）
api: to_physics_dyn, is_five, to_physics, need_physics, self_check
const: FIVE, PHYSICS, FAMILY_TO_PHYSICS
impl: self_check → _chk → need_physics → to_physics；内部helper 1个
down: _solver_chain
edit: _solver_chain   # 改_family_map须同步核对这些文件
rule: T88
why : IMPROVE__family_map.md
