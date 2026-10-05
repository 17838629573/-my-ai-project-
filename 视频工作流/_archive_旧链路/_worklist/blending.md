# FILL blending   缺 3 槽位   （模型只填 pick，勿写散文）

## 处境 (context)
已填: 无
  [IMPROVE:IMPROVE_blending.md:L27] 旧实现 `chain_response_multi` 在**振幅域**做 `sqrt(ΣA²)`——错。
  pick: IMPROVE_blending.md:27

## 收益 (achieve)
已填: 无
  [IMPROVE:IMPROVE_blending.md:L9] 相位不可定义 → 套 SRSS 无物理依据。
  [IMPROVE:IMPROVE_blending.md:L23] additive = 其余驱动，必须以差值形式参与（位移相对本级的静止位）
  [IMPROVE:IMPROVE_blending.md:L30] ## 铁律43：为什么不能末帧加时长
  [IMPROVE:IMPROVE_blending.md:L40] > **per-frame time**，不能靠复制端点（会变成 invisible technical debt）。
  pick: IMPROVE_blending.md:23

## 代价 (accepting)
已填: 无
  [IMPROVE:IMPROVE_blending.md:L23] additive = 其余驱动，必须以差值形式参与（位移相对本级的静止位）
  [IMPROVE:IMPROVE_blending.md:L45] 闭合检验  d(last, first) ≤ 内部相邻差均值 × 1.5
  pick: IMPROVE_blending.md:45
