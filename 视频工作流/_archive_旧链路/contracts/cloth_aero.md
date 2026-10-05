[S] cloth_aero @ATOM/aero  d1  in=1  gen:contract_gen
does: cloth_aero — 布料/衣物气动受力（"衣服被风吹飞"这类需求）
api: wind_force, will_blow_off, self_check
const: G
impl: self_check → _rho → will_blow_off → wind_force；内部helper 3个
up: param_decl
down: cloth_wire
edit: cloth_wire,param_decl   # 改cloth_aero须同步核对这些文件
rule: T99
why : IMPROVE_cloth_aero.md
