# render_v4 ·黄 主入口 全片编排

接口: make_parts, SHOTS, build_engine, main, **self_check**

**self_check()（铁律26）**
`python3 render_v4.py` 默认跑 self_check，**不渲染**。
真渲染须显式 `--render`（否则批跑会因渲染全片超时）。
自检项（全部只读，无渲染）：
  1. SHOTS 三轴（景别/角度/运动）声明齐全且合法
  2. 每个 shot 的 bg 文件存在
  3. actors 门禁：所有声明动作均可驱动，驱动不了即 HALT
  4. build_engine() 可构建且按需调度表正常
  5. 【铁律19】默认输出名不得是历史成片名（防复用旧产物）
SHOTS字段: name/bg/shot_type/angle/movement/look/caption/seconds/
           has_walk/has_wind/**actors**
禁止手填 char_px / bg_speed —— 一律由 photo_rules 反算
actors: [(actor,action),...]，驱动不了即 HALT（见 contracts/actors.md）

状态：黄（有契约 + self_check 且 5 项全 PASS）→ 有渲染实测证据后转绿
