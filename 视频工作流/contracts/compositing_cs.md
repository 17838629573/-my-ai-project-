# 契约：合成与出片的色彩空间 / 编码器

## 依赖 / 被依赖
- 依赖：numpy, PIL, cv2
- 被依赖：build_video

## 改前必读
- IMPROVE_compositing_cs.md

## 铁律
- 104 合成必须在线性光空间做：sRGB解码 → 预乘alpha → Porter-Duff Over → 回sRGB。
  禁止在 sRGB 编码值上直接加权平均（50%光的正确值是188，编码域直插给128，差60级）。
- 105 接触阴影同样在线性光乘，不能在编码域乘。
- 106 resize 分方向：缩小走线性光；放大不走线性光（线性光放大加重负瓣halo，画质更差）。
- 107 出片编码器用 H.264(libx264/avc1)，CRF 18-28；mp4v 是 MPEG-4 Part2，仅作回退。
