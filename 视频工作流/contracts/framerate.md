# framerate ·黄 帧率/时间基准（单一数据源）
史:notes/physics.md

## 铁律28：帧率单一数据源，输出定死 60fps
```
FPS = 60    ← 全局唯一，禁止任何文件再写 24/30
理由：离线渲染，60fps 观感更顺；且不必为每个帧率重生成序列帧
```
禁止：
- `dt = 1.0/60.0` 写死（应 `dt = 1.0/ctx.fps`，ctx.fps 由 FPS 注入）
- `scroll_per_frame(char_px, fps=60)` 默认参数（应取 ctx.fps）
- 任何 `WALK_FPS`/`FILM_FPS` 之类第二帧率常量

## 铁律29：序列帧数由物理周期反算，禁止拍脑袋
```
N = round(T_phys × FPS)
T_phys 来自 anchor.py（由 St 数推出，非手填）
```
实测反例（幡旗）：
```
T_phys = 0.585 s (f=1.708Hz)
N=24 @60fps → 一圈 0.400s → 实际 2.500Hz → 比物理快 46.4%  ← 制造帧数
正确 N = round(0.585×60) = 35 帧
```

## 铁律30：播放速率兜底
素材帧数 ≠ 应有帧数时，用 Distance Matching 播放速率钳制 ±15%。
超出即报错，禁止静默变速（否则帧数又反过来决定频率）。

## 接口
```
FPS                       全局帧率常量（唯一）
frames_for_period(T, fps) 周期 -> 应有帧数
playrate(actual, want)    实际帧数/应有帧数 -> 播放速率（钳制或报错）
```

状态：黄（有契约 + 自检）→ 有渲染实测证据后转绿
