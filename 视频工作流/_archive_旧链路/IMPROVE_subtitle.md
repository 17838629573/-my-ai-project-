# WHY subtitle   (结构化·禁散文)

meta: tier=SHOT/sub | 323行 | 上游1 下游2

## basis 依据（搜证值/公式出处；改常数前必看）
- 铁律28：fps 单一数据源，禁止写死 24（原写死 24 与输出 60fps 不一致
- 铁律26：无自检 = 不通过。契约见 contracts/subtitle.md
- 1) 字号 = 画面高 5% ±1%（GY/T357-2021）
- 4) 铁律28：fps 单一数据源

## trap 坑（勿回退 / 已修 / 冲突）
- 铁律28：fps 单一数据源，禁止写死 24（原写死 24 与输出 60fps 不一致
- -> CPS 判据按错误帧率算）。

## intent 意图（为何存在）
字幕渲染层 —— 修一个真 bug

## impact 改动影响（改本模块须回头验）
- 直接下游: film_assemble, systems_view
- 验证命令: python3 impact.py subtitle
