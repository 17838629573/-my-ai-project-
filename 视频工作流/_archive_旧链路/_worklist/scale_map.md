# FILL scale_map   缺 7 槽位   （模型只填 pick，勿写散文）

## 处境 (context)
已填: 无
  (无候选 —— 若确无，填 `NEW: N/A 无记录`)
  pick: NEW: 统一各物体真实尺寸与像素的映射，防止比例失调

## 问题 (facing)
已填: 无
  [IMPROVE:IMPROVE_scale_map.md:L4] 1. 问卷原不问真实尺寸 → AI 凭印象填像素 → 旗比城门大 2.3 倍
  [IMPROVE:IMPROVE_scale_map.md:L5] 2. inventory 用 `name`、assemble 用 `物体` → 两阶段键名不一致，已用 `_qname()` 归一
  [IMPROVE:IMPROVE_scale_map.md:L6] 3. composite 自检空 FAIL 也打印标题 → 误导为失败，已修
  [scale_map.py:L20] 默认容差：由 AI 声明可覆盖（铁律32，不写死在逻辑里）
  [scale_map.py:L158] 用 AI 搜证的唐代真实尺寸构造（非硬编码常量，仅自检用例）
  pick: IMPROVE_scale_map.md:4

## 决定 (decided)
已填: 无
  [IMPROVE:IMPROVE_scale_map.md:L5] 2. inventory 用 `name`、assemble 用 `物体` → 两阶段键名不一致，已用 `_qname()` 归一
  [scale_map.py:L62] 落位：站立物底边贴 baseline；悬挂物用 anchor_y_px 作顶边
  [scale_map.py:L158] 用 AI 搜证的唐代真实尺寸构造（非硬编码常量，仅自检用例）
  [scale_map.py:L177] 1 命名参照物唯一：所有物体像素必须由它推出
  [scale_map.py:L193] 4 旗帜不再失调：0.9m 旗应远小于 8m 城门
  pick: IMPROVE_scale_map.md:5

## 否决方案 (neglected)
已填: 无
  [IMPROVE:IMPROVE_scale_map.md:L4] 1. 问卷原不问真实尺寸 → AI 凭印象填像素 → 旗比城门大 2.3 倍
  [IMPROVE:IMPROVE_scale_map.md:L9] - composite 落位仍收原始像素，未按 target_px resize（下一步）
  pick: IMPROVE_scale_map.md:4

## 收益 (achieve)
已填: 无
  [scale_map.py:L20] 默认容差：由 AI 声明可覆盖（铁律32，不写死在逻辑里）
  [scale_map.py:L197] 5 verify 能拦住 2.3 倍失调（本轮真实 bug）
  pick: scale_map.py:197

## 代价 (accepting)
已填: 无
  [IMPROVE:IMPROVE_scale_map.md:L6] 3. composite 自检空 FAIL 也打印标题 → 误导为失败，已修
  [scale_map.py:L20] 默认容差：由 AI 声明可覆盖（铁律32，不写死在逻辑里）
  pick: NEW: composite 落位仍收原始像素未按 target_px resize（IMPROVE_scale_map.md:9 待办）

## 依据出处 (basis)
已填: 无
  [scale_map.py:L158] 用 AI 搜证的唐代真实尺寸构造（非硬编码常量，仅自检用例）
  [scale_map.py:L183] 2 落地物底边全部贴 baseline（业界：feet on y=82 防弹跳）
  pick: scale_map.py:158
