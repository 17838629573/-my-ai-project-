[S] param_decl @ATOM/rule  d0  in=3  gen:contract_gen
does: param_decl — 参数声明与反问接口
api: verify, require, have, save, audit, self_check
const: _HERE, PARAMS_FILE
impl: self_check → _load → require → save；内部helper 1个
down: _surface,cloth_aero,cloth_wire
edit: _surface,cloth_aero,cloth_wire   # 改param_decl须同步核对这些文件
rule: T99 T100 T101
why : IMPROVE_param_decl.md
