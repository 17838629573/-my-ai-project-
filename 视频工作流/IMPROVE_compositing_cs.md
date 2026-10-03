# 合成/出片 改进记录

## 为什么改
原实现是自己造的，违反业界三条硬规范。

## 业界依据
- W3C Compositing / Porter-Duff：先 straight alpha → 预乘项 → 线性光合成 → 回编码域。
  官方说明"encoded-domain 与 linear-light 结果 intentionally differ"。
- ImageMagick 官方用法：缩小必须走线性光；**放大不要走线性光**（负瓣 halo 更严重）。
- FFmpeg：H.264(libx264) 是通用标准，CRF 18-28。mp4v = MPEG-4 Part2，属古董编码器。

## 实测
- 半黑半白 50% 光：正确 sRGB = 188，旧直插给 128（差 60 级 → 半透明边缘发灰）
- 棋盘格缩小均值：线性光 187.8 ✓

## 遗留
- remap(INTER_LINEAR) 仍在 sRGB 域，可做线性光版本（收益小于 resize，未做）
- 摆动/风位移的亚像素重采样同样在 sRGB 域
