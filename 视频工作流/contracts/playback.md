# 契约块：playback（序列帧播放 / flipbook）

状态：黄（有契约 + 有自检接口）

## 这一块干什么
把 solver 算出的周期与逐帧时长，变成"第 i 个渲染帧该显示第几张素材"。
素材张数 mat_frames 与渲染帧数 frames 是两个数，播放端必须同时处理。

## 接口
- `frame_index(t, durations)` -> (i0, i1, f)  当前时刻取哪两张素材 + 插值系数
- 播放端入口：`systems.update_movables(ctx, i, t)`

## 硬约束（改这块前先读）
1. **播放端必须消费 solver 的 frame_durations**，禁止自己用
   `(i/fps)/period*n` 线性取帧——那是假定均匀且与 frame_durations 脱钩，
   改了 solver 等于没改（断链）。
2. **边界从索引算，禁止累加舍入**。业界明确：
   "Do not accumulate rounded timestamps... Calculate each boundary from its index"
   `start_i = Σ durations[:i]`（前缀和），不要用 `t += d` 迭代累加。
3. **周期为唯一真源**：`Σ durations == period_s`（±1e-9）。
   一圈的时长由物理周期定，不由素材张数定（铁律29）。
4. **均匀是默认**：`durations = [T/N] * N`。
   非均匀只在 `intentional_hold=True` 时出现（AI 显式声明"这里要有意停顿"）。
5. **接缝停顿先查重复端点**：业界原话
   "If the pause happens only at the seam, look for an accidental duplicate endpoint"。
   末帧若 ≈ 首帧，是应该被移除的重复端点，不是该加时长的地方。
6. 素材张数不足时按 playrate 钳制（铁律30），±15% 外报错，禁静默变速。

## 三个易混的数（业界原话，必须分清）
| 数 | 含义 | 谁定 |
|---|---|---|
| Source FPS | 素材采样率 | 无关，本流程不用 |
| mat_frames | 素材张数（图集格子数） | 代码，只影响平滑度 |
| frames / FPS | 渲染帧数与帧率 | 代码，与物理周期绑定 |

`duration_seconds = frame_count / playback_fps`

## 自检要求
- `Σ frame_durations == period_s`
- `frame_index` 在 t=0 / t=T/2 / t→T 边界正确（不越界、不抖）
- 前缀和版本与累加版本在 N=35 时差异 < 1e-9（证伪累加舍入）
- 重复端点检测：末帧==首帧时能识别出来

## 依赖
- framerate（playrate 钳制）
- solver（frame_durations 来源）
