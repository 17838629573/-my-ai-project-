# 契约：风与步态统一口径

## 依赖关系
- 依赖：`_common.py`（唯一定义 BEAUFORT / 旗帜频率 / 步态周期）
- 被依赖：`physics.py`, `environment.py`, `physics_rules.py`,
           `_solver_chain.py`, `actors.py`, `pose.py`, `build_video.py`

## 改前必读
- `IMPROVE_wind_unified.md`（三套 beaufort 打架实证 + 旗帜频率系数错 13 倍）
- 铁律70：物性由 AI 搜证传入，代码不内置

## 铁律88：风级判定唯一
BEAUFORT 表只在 `_common.py` 定义。physics / environment /
physics_rules 三处旧实现一律改为调用 `beaufort_scale()`，
禁止各写一份。判据：同风速三套实现必须给出同一风级。

## 铁律89：旗帜频率走 regime，不用裸 Strouhal
`flag_undulation_period(L,u,c=0.33)` 已废弃。
理由：Strouhal 给的是涡脱落高频颤动（10-40Hz），
不是整体飘扬。旧公式 T=c·L/u 相当于 St=3.0，
而文献 St_L≈0.23，导致频率快约 13 倍。
新：`flag_motion(regime,u)` 按 regime 查表，
返回 (周期s, 幅度比A/L, 颤动叠加Hz|None)。

## 铁律90：步态靠数值切换，不改代码
走路/跑步/站立一律改 gait 三元组
(speed_m_s, stride_m, swing_height_m)：
- cycle_s = stride_m / speed_m_s   ← 铁律69 强制
- cadence = 120 / cycle_s
- stride 上限 2·腿长/stance_ratio，越界由 hip_height 抛错
禁止为跑步新增分支代码。
