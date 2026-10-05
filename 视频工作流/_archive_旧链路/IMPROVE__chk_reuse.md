# WHY _chk_reuse   (结构化·禁散文)

meta: tier=SOLVE/check | 106行 | 上游1 下游1

## basis 依据（搜证值/公式出处；改常数前必看）
- ---- 复用规划（铁律49-53，契约 contracts/reuse.md）----
- 41)【铁律51】缺镜像锚点必须报错
- 42)【铁律49】半周期镜像：正弦 N=8 -> 生成 4 张
- 44)【铁律50】反对称被破坏时拒绝镜像（注入二次谐波，恒定偏置补偿不掉）
- 46)【铁律31/53】layer_plan 缺 base 报错
- 50)【铁律49】gen_n <= play_n，防省了个寂寞（历史 bug：素材 16 张却要生 17）

## trap 坑（勿回退 / 已修 / 冲突）
- 41)【铁律51】缺镜像锚点必须报错
- 46)【铁律31/53】layer_plan 缺 base 报错
- 47) overlay 缺 anchor 报错
- 50)【铁律49】gen_n <= play_n，防省了个寂寞（历史 bug：素材 16 张却要生 17）

## intent 意图（为何存在）
检查域8：复用规划/镜像/layer_plan/overlay/additive_offset。

## impact 改动影响（改本模块须回头验）
- 直接下游: solver_check
- 验证命令: python3 impact.py _chk_reuse
