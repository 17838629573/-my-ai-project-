# WHY physics   (结构化·禁散文)

meta: tier=ATOM/phys | 258行 | 上游2 下游11

## basis 依据（搜证值/公式出处；改常数前必看）
- 形状系数 k：A = k * V^(2/3)。由实测反推（人0.70m2/70kg、马2.50m2/400kg）

## trap 坑（勿回退 / 已修 / 冲突）
- ? 待补

## intent 意图（为何存在）
physics.py —— 物理原子层（逻辑唯一实现，数值全外置）

## impact 改动影响（改本模块须回头验）
- 直接下游: _chk_base, _solver_chain, actors, environment, render_desert_banner, render_gate_banner, render_v4, systems, systems_phys, systems_selfcheck, systems_view
- 验证命令: python3 impact.py physics
