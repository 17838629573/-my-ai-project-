# WHY character_sheet   (结构化·禁散文)

meta: tier=SHOT/sheet | 324行 | 上游2 下游6

## basis 依据（搜证值/公式出处；改常数前必看）
- 【按内容裁剪】行业标准 6-12 个；本片叙事实际只需要 6 个。
- 【行业标准】contact / down / passing / up × 左右镜像 = 8 帧
- 【成熟方案 · 来源已核】sprite sheet 业界一致约定：
- 实测确认：sorted(['xz_walk_2','xz_walk_10']) == ['xz_walk_10','xz_walk_2']

## trap 坑（勿回退 / 已修 / 冲突）
- 禁止凭空把 missing 写成 ok —— 那等于造假。

## intent 意图（为何存在）
角色图集 + 映射层

## impact 改动影响（改本模块须回头验）
- 直接下游: _actor_audit, enforce_cmds, film_assemble, render_desert_banner, render_gate_banner, render_v4_main
- 验证命令: python3 impact.py character_sheet
