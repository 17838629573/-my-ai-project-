# 契约块 blending — 多驱动叠加 与 循环闭合

## 铁律

- **铁律42（修订）**：多驱动用 **Additive**，不用 SRSS。
  叠加在**位移域**：`A_i(t) = A_base(t) + Σ w_j·A_j(t - φ_j)`。
  additive 必须是 **difference clip**（相对中性姿态的变化量），缺 ref 即报错。
- **铁律43（修订）**：循环闭合 = **移除重复端点**，不是末帧加时长。
  循环时长 `T = 唯一帧数 / 播放fps`；
  闭合检验 `d(last, first) ≤ 内部相邻差均值 × 1.5`，
  超出 = 缺过渡姿态，应补生成，不是改时长掩盖。
  有意 hold 用 per-frame duration 显式声明 `intentional_hold=True`。

（推翻理由与业界原文见 `IMPROVE_blending.md`）

## 接口

```python
chain_response_multi(links, drives, ...)
    # drives: [(f_hz, amp_m, name), ...] 第一个为 base，其余 additive
    # 返回各级：amp_m、amp_by_drive、phase_lag_deg

frame_durations(N, T, tail_ratio=1.0, intentional_hold=False)
    # 默认均匀：每帧 T/N
    # intentional_hold=True 时末帧 ×tail_ratio，并反解基础帧长使总长仍 = T
```

## 自检

1. 单驱动退化为原值（factor=0 等价）
2. 双驱动：峰值位移 ≥ 任一单驱动峰值（叠加不小于分量）
3. additive 必须带 ref（中性姿态），缺失即报错

## 依赖

- `framerate`（FPS）、`anchor`（物理点）

## 改前必读

`IMPROVE_blending.md`
