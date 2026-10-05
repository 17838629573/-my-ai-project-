# WHY build_phase_render   (结构化·禁散文)

meta: tier=BUILD/phase | 70行 | 上游3 下游1

## basis 依据（搜证值/公式出处；改常数前必看）
- 树（程序化风摆，铁律79）
- 三人：沿路径弧长推进（铁律76/77）

## trap 坑（勿回退 / 已修 / 冲突）
- 【已删】TREE_XY 硬编码落点 —— 树被钉在墙体立面上，与 spec 声明的地面锚点冲突。
- 树锚点一律由 ctx["tree_xy"] 传入（来自 spec 声明的 anchor_xy），禁代码写死。

## intent 意图（为何存在）
出片：逐帧合成循环。

## impact 改动影响（改本模块须回头验）
- 直接下游: build_video
- 验证命令: python3 impact.py build_phase_render
