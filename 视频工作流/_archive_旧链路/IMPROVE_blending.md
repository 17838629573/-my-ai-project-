# IMPROVE_blending — 多驱动叠加与循环闭合详解

契约 `contracts/blending.md` 只留铁律与接口；本文存放**推翻理由与业界原文**。

## 铁律42：为什么推翻 SRSS

【推翻】上一版用 SRSS（反应谱平方和开方）叠加 gait + wind。
SRSS 属地震工程**非相干随机振动**定式，而步频与风都是**确定性周期驱动**，
相位不可定义 → 套 SRSS 无物理依据。

【业界定式】Qt 3D `AdditiveClipBlend` / Unity Animation Layer Additive 模式：

    resultClip = baseClip + additiveFactor × additiveClip

关键约束（Qt 文档原文）：
> additiveClip 必须是 **difference clip** —— 只含"相对中性姿态的变化量"，
> 不是完整姿态。否则 result 会跳变/不自然。
> additiveFactor ∈ [0,1]；0 时退化为 base。

【本工程映射】
```
base     = 主驱动（chain 链首驱动，第一个 drive）
additive = 其余驱动，必须以差值形式参与（位移相对本级的静止位）
叠加域   = 位移域，不是振幅域
```

旧实现 `chain_response_multi` 在**振幅域**做 `sqrt(ΣA²)`——错。
振幅域相加丢相位，等于把两个周期驱动当噪声。

## 铁律43：为什么不能末帧加时长

【推翻】上一版 `frame_durations` 给末帧 ×1.8 时长。

framesprite 权威原文：
> "Should a loop include the first frame again at the end? **Usually no.**
>  The engine returns from the last unique frame to the first automatically."
> "Remove duplicate endpoints" —— 末帧与首帧相同则被显示两次，
> 表现为**每圈顿一下**。
> "Separate a designed hold from a duplicate" —— 有意停顿须用
> **per-frame time**，不能靠复制端点（会变成 invisible technical debt）。

【正确判据】
```
循环时长  T = 唯一帧数 / 播放fps    （不是素材张数决定）
闭合检验  d(last, first) ≤ 内部相邻差均值 × 1.5
          超出 = 缺过渡姿态，应补画/补生成，不是改时长掩盖
```

若确实需要 hold（如冲击后停驻）：用 per-frame duration 表显式声明，
并注明 "intentional hold"，与 accidental duplicate 区分。

【保留】`frame_durations` 函数名保留，语义改为**均匀帧长**（默认）；
`tail_ratio` 仅当 AI 显式声明 `intentional_hold=True` 时才启用。

## 历史踩坑

1. **frame_durations 算了却没人用** —— 成片吃的是硬编码周期。
   同一类断链后来在风周期（`T_flag` 键从不产出）上又出现一次。
   教训：契约写了产出项，必须有调用方校验，否则等于没写。

---

---

---
## Y-Statement（gen:why_apply 勿手改）

meta: blending
处境: 旧实现 `chain_response_multi` 在**振幅域**做 `sqrt(ΣA²)`——错。
问题: > **per-frame time**，不能靠复制端点（会变成 invisible technical debt）。
决定: 【保留】`frame_durations` 函数名保留，语义改为**均匀帧长**（默认）；
否决方案: 旧实现 `chain_response_multi` 在**振幅域**做 `sqrt(ΣA²)`——错。
收益: additive = 其余驱动，必须以差值形式参与（位移相对本级的静止位）
代价: 闭合检验 d(last, first) ≤ 内部相邻差均值 × 1.5
依据出处: 相位不可定义 → 套 SRSS 无物理依据。
