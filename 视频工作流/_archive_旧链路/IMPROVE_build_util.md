# WHY build_util   (结构化·禁散文)

meta: tier=BUILD/util | 205行 | 上游13 下游5

## basis 依据（搜证值/公式出处；改常数前必看）
- ? 待补（改常数前必补）

## trap 坑（勿回退 / 已修 / 冲突）
- 【已修】拆分时漏算了画布尺寸：W/H 未定义 → NameError。
- 【已修】pose.solve 返回世界坐标（人整体前进 speed*t）。
- 【已修】足端语义必须逐帧给出：旧实现只在末尾追加一次 t=0 的值，

## intent 意图（为何存在）
build_video 的自检/检查逻辑（由 _extract_tool.py 从 build_video.py 抽出）

## impact 改动影响（改本模块须回头验）
- 直接下游: build_phase_asset, build_phase_gen, build_phase_render, build_phase_setup, build_video
- 验证命令: python3 impact.py build_util
