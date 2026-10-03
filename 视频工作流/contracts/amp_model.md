# 契约块：amp_model（振幅比模型）

**状态**：黄（有契约，有自检，缺实测成片证据）
**负责**：solver.amp_over_L / anchor.build_anchor / anchor.strouhal_freq
**依赖**：physics（beaufort_level）→ 无环

---

## 铁律45：振幅比 A/L 必须随风速变化，且调用链全程传导

### 问题（实测发现，非设计）

`A/L = 1.6` 是 Izawa 2024 测得的 **flapping 态**峰峰振幅比。
旧代码把它当**无条件常数**写死在 `anchor.A_OVER_L`，导致：

```
3 级风(U=4.4) 的旗，摆幅 = 6 级风(U=12.3) 的旗
→ 小风也画成大风形态（"重旗软趴趴"被画成"大幅抽打"）
```

**更要命的是断链**：solver.py 已按风级查表算出 `aol`，
但调用 `anchor.build_anchor()` 时该值**传不进去**——
build_anchor 签名无 `a_over_l` 形参，内部直接用模块常数 `A_OVER_L * L`。
**查表算了等于没算。**（典型的"改了等于没改"）

### 物理依据（搜索所得，非自创）

**孙传宝、贾来兵、尹协振《单个柔性旗帜在均匀流中摆动的测力实验》
实验流体力学 2011, 25(6)**（中国科大，低速风洞测力天平 + 高速摄影）：

> 影响无量纲参数主要是宽长比 H\*、质量比 M\*、无量纲速度 U\*。
> 保持 H\* 不变、改变 M\* 时，Cd、A\* 和 St **都随 U\* 先增大后趋于定值**。
> 保持 M\* 不变、改变 H\* 时，Cd、A\* 和 St **都随 U\* 线性增大**。
> 实验证明：旗帜受到的阻力与摆动振幅成正比。

**NOAA JetStream 蒲福表**（权威定性锚点）：

| 风级 | 旗帜形态原文 |
|---|---|
| 3 | wind **extends light flag**（轻旗被吹展开）|
| 4 | raises dust and loose paper（未提旗，灰尘起）|
| 6 | large branches in motion（大枝摇动）|

结论：**A\* 随 U\* 单调增但饱和**（不是无限增大），且存在**起振临界**。

### 硬约束

1. `A/L` **必须**由风级查表得到，表由 AI 搜证传入（`criteria.amp_by_level`），
   代码只做查表与插值——**代码不得内置任何 A/L 数值**（铁律32）。
2. 查表结果 `aol` **必须**沿调用链传导到最终几何：
   `solve → build_anchor → tip_pp_amp_m → skeleton_points`
   **中间任何一层回退常数即断链，自检必须 FAIL。**
3. `build_anchor` 必须显式声明 `a_over_l` 形参，**禁止**在函数体内引用 `A_OVER_L` 模块常数。
4. 饱和性：查表值随风级单调不减，且存在上限（≤1.6，Izawa flapping 实测）。

### 接口

```python
amp_over_L(level, criteria) -> float   # 查表，AI 传表
build_anchor(..., a_over_l=None)       # None → 报错，禁静默取默认
strouhal_freq(U, L, a_over_l=None)     # 同上
```

### 自检（必须包含）

- A/L 随风速递增且非恒定（已有，项 29）
- **build_anchor 传入 a_over_l 与不传的结果不同**（新增，防断链回归）
- 源码扫描：`build_anchor` 函数体内不得出现 `A_OVER_L`（新增）
