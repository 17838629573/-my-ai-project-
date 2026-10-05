# WHY enforce_cmds   (结构化·禁散文)

meta: tier=GATE/core | 298行 | 上游3 下游1

## basis 依据（搜证值/公式出处；改常数前必看）
- 6) 【铁律12盲区】import 可达性：deps.md 声明了，文件却没写 import

## trap 坑（勿回退 / 已修 / 冲突）
- 【已修】cs.missing_assets() 是旧剧本（通缉文牒/瘦老赤马…）的硬编码清单，
- 旧清单仅作提示，不再阻断渲染。
- 【已修】旧版硬编码 8 个背景名(gate/hall/...)，换场景即永久 FAIL。
- 【已修】15%下限是人物全身判据。道具/动物在白底上本就占屏小，

## intent 意图（为何存在）
enforce 的自检/检查逻辑（由 _extract_tool.py 从 enforce.py 抽出）

## impact 改动影响（改本模块须回头验）
- 直接下游: enforce
- 验证命令: python3 impact.py enforce_cmds
