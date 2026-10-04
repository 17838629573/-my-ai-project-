# WHY anchor   (结构化·禁散文)

meta: tier=ATOM/path | 284行 | 上游1 下游3

## basis 依据（搜证值/公式出处；改常数前必看）
- 【铁律45】A_OVER_L 不再是常量 —— 已删除。
- 旧值 1.6 是 Izawa 2024 测得的 **flapping 态**峰峰振幅比，
- 现值必须由调用方显式传入（a_over_l 形参），来源 = 风级查表，
- 表由 AI 搜证传入（铁律32）。函数体内引用本名即视为断链回归。
- regime 区间（Izawa 2024 实测）
- 7. 铁律29：序列帧数由周期反算，不得手填 24

## trap 坑（勿回退 / 已修 / 冲突）
- 旧值 1.6 是 Izawa 2024 测得的 **flapping 态**峰峰振幅比，
- 旧实现内部硬用常数 1.6，solver 查表值传不进来 —— 查了等于没查

## intent 意图（为何存在）
anchor.py —— 物理点锚点层

## impact 改动影响（改本模块须回头验）
- 直接下游: _chk_base, _solver_chain, _solver_geom
- 验证命令: python3 impact.py anchor
