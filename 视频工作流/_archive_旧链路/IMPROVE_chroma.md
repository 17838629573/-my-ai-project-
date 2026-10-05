# WHY chroma   (结构化·禁散文)

meta: tier=ATOM/img | 290行 | 上游1 下游8

## basis 依据（搜证值/公式出处；改常数前必看）
- 自动取四角均值作参考色（实测背景均匀）
- 铁律26：无自检 = 不通过。契约见 contracts/chroma.md

## trap 坑（勿回退 / 已修 / 冲突）
- ? 待补

## intent 意图（为何存在）
角色层素材处理：色度键抠像 + 去溢色 + 边缘处理

## impact 改动影响（改本模块须回头验）
- 直接下游: _split_sheet, build_phase_asset, build_util, build_video, character_sheet, chroma_selfcheck, enforce_cmds, film_assemble
- 验证命令: python3 impact.py chroma
