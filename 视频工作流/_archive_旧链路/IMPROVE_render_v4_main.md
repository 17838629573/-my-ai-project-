# WHY render_v4_main   (结构化·禁散文)

meta: tier=SHOT/_top | 195行 | 上游2 下游1

## basis 依据（搜证值/公式出处；改常数前必看）
- 5) 铁律19：默认输出名不得是历史成片

## trap 坑（勿回退 / 已修 / 冲突）
- 3) actors 门禁（驱动不了即 HALT，禁降级）
- 【修复】--only 模式曾把磁盘残留的旧段一并合并，

## intent 意图（为何存在）
render_v4 自检与出片主流程（原 182 行上帝函数抽出）。

## impact 改动影响（改本模块须回头验）
- 直接下游: render_v4
- 验证命令: python3 impact.py render_v4_main
