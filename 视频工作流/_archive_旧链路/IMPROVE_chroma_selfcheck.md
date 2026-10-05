# WHY chroma_selfcheck   (结构化·禁散文)

meta: tier=ATOM/img | 128行 | 上游1 下游1

## basis 依据（搜证值/公式出处；改常数前必看）
- 5) 铁律15：形状合理性
- ⚠ 已知局限（实测）：纯几何拦不住历史那个 bug ——
- （铁律18）。这里同时输出主色供人工/AI 复核。

## trap 坑（勿回退 / 已修 / 冲突）
- ⚠ 已知局限（实测）：纯几何拦不住历史那个 bug ——

## intent 意图（为何存在）
chroma 的自检/检查逻辑（由 _extract_tool.py 从 chroma.py 抽出）

## impact 改动影响（改本模块须回头验）
- 直接下游: chroma
- 验证命令: python3 impact.py chroma_selfcheck
