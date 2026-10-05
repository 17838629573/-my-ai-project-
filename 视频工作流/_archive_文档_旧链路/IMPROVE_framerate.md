# WHY framerate   (结构化·禁散文)

meta: tier=ATOM/frame | 308行 | 上游0 下游17

## basis 依据（搜证值/公式出处；改常数前必看）
- ── 铁律28：全局唯一帧率 ────────────────────────────────────
- ── 铁律30：Distance Matching 播放速率钳制（业界 ±15%）────────
- 2) 铁律29：帧数由周期反算
- 4) 铁律30：超出钳制必须报错
- N) 播放时序（铁律46，契约 contracts/playback.md）

## trap 坑（勿回退 / 已修 / 冲突）
- 1) 全局帧率唯一性：扫描活跃代码，禁止第二帧率常量
- 4) 铁律30：超出钳制必须报错
- 5) 合法范围内不报错
- 不 import solver：framerate 是 solver 的下游，反向依赖会成环（门禁已拦）

## intent 意图（为何存在）
framerate.py —— 帧率/时间基准（单一数据源）

## impact 改动影响（改本模块须回头验）
- 直接下游: _chk_base, _solver_chain, _solver_chain_aux, anchor, build_phase_render, build_util, build_video, film_assemble_render, loop_engine, render_desert_banner, render_gate_banner, render_v4, subtitle, systems, systems_phys, systems_selfcheck, systems_view
- 验证命令: python3 impact.py framerate
