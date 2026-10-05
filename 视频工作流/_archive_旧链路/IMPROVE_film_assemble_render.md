# WHY film_assemble_render   (结构化·禁散文)

meta: tier=SHOT/assemble | 178行 | 上游2 下游1

## basis 依据（搜证值/公式出处；改常数前必看）
- 3) 铁律28：fps 单一数据源
- 4) broken 过滤必须【真的改变结果】（铁律13：空转检查不算证据）
- 铁律28：fps 单一数据源，禁止写死 60

## trap 坑（勿回退 / 已修 / 冲突）
- 铁律28：fps 单一数据源，禁止写死 60

## intent 意图（为何存在）
film_assemble 分镜渲染与自检（原 165 行抽出）。

## impact 改动影响（改本模块须回头验）
- 直接下游: film_assemble
- 验证命令: python3 impact.py film_assemble_render
