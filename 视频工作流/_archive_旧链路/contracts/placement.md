[S] placement @ATOM/path  d0  in=3  gen:contract_gen
does: 语义定位点：把一个语义点 → 世界坐标落位。
api: semantic_point, attach_point, place, verify, self_check
const: SEMANTIC_KINDS, _SPEC
impl: self_check → place → semantic_point → verify
down: build_util,build_video,shot_plan
edit: build_util,build_video,shot_plan   # 改placement须同步核对这些文件
rule: T73 T74
why : IMPROVE_placement.md
