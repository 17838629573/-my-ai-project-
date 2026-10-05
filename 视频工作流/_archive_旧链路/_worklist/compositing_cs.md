# FILL compositing_cs   缺 5 槽位   （模型只填 pick，勿写散文）

## 处境 (context)
已填: 无
  [IMPROVE:IMPROVE_compositing_cs.md:L4] 原实现是自己造的，违反业界三条硬规范。
  pick: IMPROVE_compositing_cs.md:4

## 问题 (facing)
已填: 无
  [IMPROVE:IMPROVE_compositing_cs.md:L9] - ImageMagick 官方用法：缩小必须走线性光；**放大不要走线性光**（负瓣 halo 更严重）。
  [IMPROVE:IMPROVE_compositing_cs.md:L13] - 半黑半白 50% 光：正确 sRGB = 188，旧直插给 128（差 60 级 → 半透明边缘发灰）
  pick: IMPROVE_compositing_cs.md:13

## 决定 (decided)
已填: 无
  [IMPROVE:IMPROVE_compositing_cs.md:L4] 原实现是自己造的，违反业界三条硬规范。
  [IMPROVE:IMPROVE_compositing_cs.md:L9] - ImageMagick 官方用法：缩小必须走线性光；**放大不要走线性光**（负瓣 halo 更严重）。
  [IMPROVE:IMPROVE_compositing_cs.md:L10] - FFmpeg：H.264(libx264) 是通用标准，CRF 18-28。mp4v = MPEG-4 Part2，属古董编码器。
  pick: IMPROVE_compositing_cs.md:9

## 否决方案 (neglected)
已填: 无
  [IMPROVE:IMPROVE_compositing_cs.md:L4] 原实现是自己造的，违反业界三条硬规范。
  [IMPROVE:IMPROVE_compositing_cs.md:L13] - 半黑半白 50% 光：正确 sRGB = 188，旧直插给 128（差 60 级 → 半透明边缘发灰）
  pick: IMPROVE_compositing_cs.md:13

## 代价 (accepting)
已填: 无
  [IMPROVE:IMPROVE_compositing_cs.md:L13] - 半黑半白 50% 光：正确 sRGB = 188，旧直插给 128（差 60 级 → 半透明边缘发灰）
  pick: NEW: remap(INTER_LINEAR) 与亚像素重采样仍在 sRGB 域，未做线性光版
