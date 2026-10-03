# IMPROVE：param_decl / cloth_aero（改这块前必读）

## 一、业界依据（已联网检索）

| 规范 | 来源 | 要点 |
|---|---|---|
| Fail Fast | Jim Shore, *Fail Fast*, IEEE Software 2004；P034 | 缺失即停，不要带病运行 |
| No Magic Defaults | 配置设计通例 | 禁止静默回填默认数 |
| Strict Unknown Values | Hypster ADR；Spring Boot `ignoreUnknownFields=false`；.NET `ErrorOnUnknownConfiguration`；Go `DisallowUnknownFields()` | 未知键默认 raise |
| 布料气动四参数 | NvCloth(O3DE) `SetWindDragCoefficient/SetWindLiftCoefficient/SetWindFluidDensity/SetWindVelocity`；Unreal `FClothConfig_Legacy.WindDragCoefficient/WindLiftCoefficient` | ρ / Cd / Cl / v 四件套 |
| 平板 Cd | Hoerner《Fluid-Dynamic Drag》，White / Munson 阻力表 | 方板正对来流 Cd 1.18–1.28（Re>1e3） |

## 二、踩过的真坑

**坑1：Bullet/ammo.js 公式量纲错了**
文档写作 `F = Cd·A·(v·n)·v`，缺 ½ 与 ρ，量纲是 m⁴/s² 而非牛顿。
→ 本模块按物理正确式 `q=½ρv²` 重写；自检第 8 项直接验证动压等于 ½ρv²。

**坑2：证伪 A 写成空转（第 N 次踩）**
第一版用 `try: fake_require()` 假装验证"静默兜底会被抓"——假函数当然不会被任何机制抓到，检查是空转的。
→ 改成 AST 扫 `require` 源码，确认不存在返回数字常量 / `or` / 三元兜底的路径。

**坑3：升力在正迎风与平行时都是 0**
`F_lift ∝ cosθ·sinθ`，正面（θ=0）与平行（θ=90°）都归零，**45° 才最大**。
→ 自检必须用斜法向（1,1），用 (0,1) 会全零导致"单调性"测试假失败。

**坑4：Cd 的两套定义并存**
物理平板 Cd≈1.28；但 NvCloth / Unreal 的 WindDrag 是 [0,1] 归一化美术参数，**不是同一个量**。
→ 本模块用物理定义；若接引擎需另做映射，不可直接套用。

## 三、实测（僧衣 A=0.8m² m=0.45kg，法向 45°）

| 风级 | 风速 m/s | 动压 Pa | 升力 N | 升力/重 | 吹飞 |
|---|---|---|---|---|---|
| 3 微风 | 4.4 | 11.9 | 3.79 | 0.86 | 否 |
| 4 和风 | 6.7 | 27.5 | 8.80 | 1.99 | **是** |
| 6 强风 | 12.3 | 92.7 | 29.65 | 6.72 | 是 |
| 8 大风 | 18.9 | 220.0 | 70.38 | 15.95 | 是 |

阈值出现在 **4 级和风**（6.7 m/s）——代码算出来的，不是我拍的。

## 四、待办

- [ ] 旧模块 14 处 `.get(key, 默认值)` 静默兜底尚未接入 `param_decl`（`_solver_reuse.py`、`composite.py`、`scale_map.py` 等）
- [ ] `cloth_aero` 尚未接入 solver / build_video，目前独立
- [ ] 引擎归一化 [0,1] 与物理 Cd 的映射未做

## 五、给 AI 的提示词（代码缺失参数时自动吐出）

> 参数缺失，禁止心里默算。你必须：①联网检索权威取值 ②给出来源（文献/标准/厂商文档）
> ③给出合理区间 [lo,hi] ④落盘写进 `params_ai.json`（value/unit/source/range/family 五项）。
> 然后由代码读取并运算 —— 你只负责提供数值和来源。
