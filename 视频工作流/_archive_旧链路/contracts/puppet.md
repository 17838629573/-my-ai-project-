[S] puppet @SHOT/skel  d3  in=0  gen:contract_gen
does: 部件化木偶（cutout puppet）—— V6 补帧的正确解法。
api: with_derived, part_transform, all_transforms, self_check
const: PARTS, DRAW_ORDER
impl: self_check → all_transforms → part_transform → with_derived
up: _common,pose
edit: _common,pose   # 改puppet须同步核对这些文件
rule: T70
why : IMPROVE_puppet.md
