"""45 项测试用例声明（测试第二步：声明）

契约: tests/cases
  输入: 无（静态声明）
  输出: CASES 列表，每项含 需求能力 / 需求判据 / 种子
  依赖: tests/harness
  被依赖: tests/run_all
  约束: 需求能力名必须与 beat.CAP 注册名一致，否则判 STUB；
        每项固定随机种子，便于复现与记录失败帧

状态语义
  STUB   需求能力未注册 → 不算失败，算未实现，附 search_hint
  READY  能力齐备，可以跑
"""
import random

# (id, 组, 名称, 需求能力, 需求判据, 种子)
CASES = [
    # ---------------------------------------------------------------- A 基础动作
    ("A1", "A", "直线行走：脚触地不滑步，手臂自然摆动",
     ["walk"], ["skate_cm_frame", "float_m", "feet_clip_m", "jitter_px", "frame_jump_ratio"], 11),
    ("A2", "A", "跑步急停：前倾后恢复，不穿地",
     ["run", "brake"],
     ["ground_penetration_m", "contact_float_m", "flight_apex_err", "frame_jump_ratio"], 12),
     # 跑步有腾空相，脚本该离地 → float_m 不成立；改在触地帧量 contact_float_m
    ("A3", "A", "原地跳跃：蹲-跳-腾空-落地缓冲",
     ["jump"], ["contact_float_m", "flight_apex_err", "energy_gain", "frame_jump_ratio"], 13),
     # 同上：跳跃整段只在触地帧量浮空；顶点用 Δs=g·T_F²/8 校验
    ("A4", "A", "转身180：头-躯干-脚顺序自然，无瞬翻",
     ["turn"], ["frame_jump_ratio", "skate_cm_frame", "jitter_px"], 14),
    ("A5", "A", "挥手：抬右臂，掌摆动，肩肘腕联动",
     ["wave"], ["elbow_reflex", "frame_jump_ratio"], 15),
    ("A6", "A", "踢球：抬腿击中，球飞出，人保持平衡",
     ["kick", "ball"], ["penetration_m", "momentum_err", "float_m"], 16),
    ("A7", "A", "下蹲捡物：蹲-手触地-拿-起",
     ["crouch", "reach_grab"],
     ["float_m", "penetration_m", "skate_cm_frame", "arm_reach"], 17),

    # ---------------------------------------------------------------- B 抓取交互
    ("B8", "B", "拿杯子：伸-握-跟随-不掉落",
     ["carry_prop"], ["penetration_m", "jitter_px", "arm_reach"], 21),
    ("B9", "B", "放下杯子：移到桌面-张指-留桌-不穿透",
     ["prop_release"], ["penetration_m", "jitter_px", "arm_reach"], 22),
    ("B10", "B", "扔球：后摆-释放-抛物线-落地反弹",
     ["throw", "ball"], ["restitution_err", "energy_gain", "penetration_m"], 23),
    ("B11", "B", "接球：预测位-接触-停-跟随手",
     ["catch", "ball"], ["penetration_m", "momentum_err", "jitter_px"], 24),
    ("B12", "B", "推箱子：箱滑动，人与箱不重叠",
     ["push", "box"], ["penetration_m", "momentum_err"], 25),
    ("B13", "B", "拉绳：抓一端-绷紧-另一端移动",
     ["rope"], ["frame_jump_ratio", "penetration_m"], 26),
    ("B14", "B", "开门：抓把手-绕铰链旋转-人不穿门",
     ["hinge_door"], ["penetration_m", "frame_jump_ratio"], 27),

    # ---------------------------------------------------------------- C 物体碰撞
    ("C15", "C", "球撞多米诺：连锁推倒",
     ["rigid_body", "toppling"], ["momentum_err", "penetration_m"], 31),
    ("C16", "C", "堆叠方块：稳定不抖不塌",
     ["stack"], ["penetration_m"], 32),
    ("C17", "C", "斜坡滚球：加速，底部平滑过渡",
     ["ramp"], ["energy_gain", "penetration_m"], 33),
    ("C18", "C", "弹球：反弹高度逐次衰减",
     ["bounce"], ["restitution_err", "energy_gain"], 34),
    ("C19", "C", "摆锤碰撞：动量传递",
     ["pendulum"], ["momentum_err", "penetration_m"], 35),
    ("C20", "C", "两球对撞：等质量交换速度，异质量守恒",
     ["rigid_body"], ["momentum_err", "penetration_m"], 36),

    # ---------------------------------------------------------------- D 多主体
    ("D21", "D", "两人击掌：手部接触不穿模",
     ["multi_actor", "contact"], ["penetration_m", "frame_jump_ratio"], 41),
    ("D22", "D", "两人传球：A扔B接再扔回",
     ["multi_actor", "throw", "catch"], ["penetration_m", "momentum_err"], 42),
    ("D23", "D", "人物与猫：猫穿腿间，不踩不穿模",
     ["multi_actor", "quadruped"], ["penetration_m", "float_m"], 43),
    ("D24", "D", "人群碰撞：三人互阻不重叠",
     ["crowd_collide"], ["penetration_m"], 44),

    # ---------------------------------------------------------------- E 复杂序列
    ("E25", "E", "跑跳抓取：跑-跳-空中抓-落地翻滚",
     ["run", "jump", "reach_grab", "roll"], ["frame_jump_ratio", "energy_gain"], 51),
    ("E26", "E", "搬运箱子：抱起-走-放下，不穿手",
     ["carry_box"], ["penetration_m", "skate_cm_frame"], 52),
    ("E27", "E", "投掷命中：扔球击中移动目标，目标倒下",
     ["throw", "toppling"], ["momentum_err", "penetration_m"], 53),
    ("E28", "E", "爬梯子：手交替握杆，脚踩踏，不滑脱",
     ["climb"], ["float_m", "penetration_m", "skate_cm_frame"], 54),
    ("E29", "E", "推倒墙壁：多方块墙散落",
     ["stack", "toppling"], ["penetration_m", "frame_jump_ratio"], 55),

    # ---------------------------------------------------------------- F 边界压力
    ("F30", "F", "快速移动：高速跑，碰撞不丢失不穿墙",
     ["run", "ccd"], ["penetration_m", "frame_jump_ratio"], 61),
    ("F31", "F", "多物体：50球同时落地互撞，不穿透不爆炸",
     ["rigid_body", "broadphase"], ["penetration_m"], 62),
    ("F32", "F", "零重力：漂浮，碰撞后匀速",
     ["gravity_off"], ["momentum_err", "penetration_m"], 63),
    ("F33", "F", "高摩擦：滑动迅速停止",
     ["friction"], ["momentum_err", "penetration_m"], 64),
    ("F34", "F", "初始重叠：应分离或报错，不闪烁",
     ["overlap_resolve"], ["penetration_m"], 65),
    ("F35", "F", "超长视频：1分钟以上，检查累积误差漂移",
     ["walk"], ["frame_jump_ratio", "jitter_px", "skate_cm_frame"], 66),
    # ---------------------------------------------------------------- G 生物运动
    ("G36", "G", "ADDITIVE 三能力接线：gaze/finger/page 叠加到 gait，下半身零污染",
     ["walk", "gaze_shift", "finger_tap", "page_flip"],
     ["lower_pollution", "frame_jump_ratio"], 67),
    ("G37", "G", "攀岩：三点支撑 / 支撑相零滑移 / 不穿壁",
     ["climb_rock"],
     ["support_min", "foot_slip_m", "ground_penetration_m", "frame_jump_ratio"], 68),
    ("G38", "G", "鱼游：脊椎段长守恒 / Strouhal 区间 / 帧间平滑",
     ["fish_swim", "fish_strouhal"],
     ["seg_len_err", "strouhal_lo", "strouhal_hi", "frame_jump_ratio"], 69),
    ("G39", "G", "四足六步态：支撑足缺口 / 足端滑移 / 帧间平滑",
     ["quadruped"],
     ["gait_contact_deficit", "foot_slip_m", "frame_jump_ratio"], 70),

    # ---------------------------------------------------------------- H 混合场景
    # 登记由来（真实回归）：H40 与 P41~P45 的执行体早已写进 run_all.EXEC，
    # 但从未登记进 CASES —— main() 只遍历 CASES，故这 6 条**从未被门检跑过**，
    # 与"climb 白写"同类（注册了却没接线），只是方向相反：有执行体无声明。
    ("H40", "H", "混合场景：7 类实体同时间轴 / 无 NaN / 跨体穿透 / 时间轴对齐",
     ["walk", "run", "ball", "rope", "quadruped", "fish_swim", "bird_fly"],
     ["nan_count", "frame_jump_ratio", "xbody_penetration_m",
      "ground_penetration_m", "min_arc_m", "time_span_err_s"], 71),

    # ---------------------------------------------------------------- P 常见物理现象
    ("P41", "P", "树叶飘落：终端速度远低于自由落体 / 水平漂移 / flutter 涌现",
     ["leaf_fall"], ["leaf_v_term_mps", "leaf_drift_m", "leaf_swings"], 72),
    ("P42", "P", "墙体开裂：断键 / 多碎块 / 碎块位移有界",
     ["fracture"], ["frac_max_disp_m", "frac_n_broken", "frac_n_frag"], 73),
    ("P43", "P", "水流冲击地面：不穿地 / 横向铺展 / 粒子不丢 / 密度收敛",
     ["water_jet"], ["water_spread_ratio", "water_rho_rel", "water_n_alive",
                     "ground_penetration_m"], 74),
    ("P44", "P", "牛顿摆：末球弹出 / 中间球窗口内静止 / 能量守恒",
     ["newton_cradle"], ["cradle_th_mid_win_rad", "cradle_th_last_win_rad",
                         "cradle_energy_err"], 75),
    ("P45", "P", "转台：离心滑移 / 被甩向外 / 科氏横向偏转",
     ["turntable"], ["turntable_r_end_m", "turntable_lateral_m"], 76),
]


def seed_of(cid):
    for c in CASES:
        if c[0] == cid:
            return c[5]
    raise KeyError(cid)


def rng(cid):
    return random.Random(seed_of(cid))
