# FILL wind_sway   缺 3 槽位   （模型只填 pick，勿写散文）

## 决定 (decided)
已填: 无
  [IMPROVE:IMPROVE_wind_sway.md:L5] ### 坑1：不能用"层间幅度差"来证伪频率分离
  [IMPROVE:IMPROVE_wind_sway.md:L6] 我第一版用 `max(parts) - min(parts)` 判断同频是否失去层次，**FAIL**。
  [IMPROVE:IMPROVE_wind_sway.md:L15] 故本模块不引入通道概念，只用层名 trunk/branch/leaf。符合铁律32（知识外置）。
  [IMPROVE:IMPROVE_wind_sway.md:L17] ### 坑3：根部权重必须为 0，否则整树在地上滑
  [IMPROVE:IMPROVE_wind_sway.md:L23] - `build_video.py` **没有树**，未调用 wind_sway
  pick: IMPROVE_wind_sway.md:17

## 收益 (achieve)
已填: 无
  [IMPROVE:IMPROVE_wind_sway.md:L5] ### 坑1：不能用"层间幅度差"来证伪频率分离
  [IMPROVE:IMPROVE_wind_sway.md:L18] 业界原话："Black/Zero Values 施加于根部，确保其牢牢锚定地面"。
  [IMPROVE:IMPROVE_wind_sway.md:L44] | 同上 | 根部零权重确保不离地；WPO 包围盒需扩展，避免风摆把顶点推出包围盒导致弹跳剔除 |
  [wind_sway.py:L15] 频率比与幅度：来自业界给定值（salivity / 菜鸟编程网），可由 cfg 覆盖
  [wind_sway.py:L26] 各层特征长度(m)，用于 wind_response 计算；可由 cfg["L_m"] 覆盖
  pick: IMPROVE_wind_sway.md:18

## 代价 (accepting)
已填: 无
  [IMPROVE:IMPROVE_wind_sway.md:L5] ### 坑1：不能用"层间幅度差"来证伪频率分离
  [IMPROVE:IMPROVE_wind_sway.md:L7] 因为这个差主要来自 `amp_ratio`（0.08/0.25/0.60），**与频率无关**。
  [wind_sway.py:L209] 13 证伪：若根部权重非 0（错误做法），整树会平移
  [wind_sway.py:L217] （不能用"层间幅度差"来度量——那主要来自 amp_ratio，与频率无关）
  pick: IMPROVE_wind_sway.md:23
