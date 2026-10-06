"""# 契约: tests.criteria
## 范围
判据阈值与出处登记表（name -> (阈值, 比较符, 出处)）。
与测量实现分离：本文件只放「尺子」，测量函数在 tests/harness.py。
拆分原因：判据表随能力增长持续变长，与测量逻辑混在一处会撑破单文件上限，
且「阈值改了」与「测量逻辑改了」是两类变更，应各自可审。

## 依赖
无（纯数据表）

## 铁律
阈值定标必须先于测试（A1）：禁止“跑不过→调阈值→补出处”。
"""

# 穿模容差（单点定义，多处引用——禁止复制粘贴传播，见 A2）
# 出处：Box2D v2.4.1 源码 include/box2d/b2_common.h:65
#       `#define b2_linearSlop (0.005f * b2_lengthUnitsPerMeter)`
# 此为官方默认值；若本机实测穿透超过它，应修物理求解器（提高迭代/减小步长），
# 而不是放宽本阈值——阈值定标必须先于测试，不得"跑不过→调阈值→补出处"（见 A1）
_SLOP = 0.005

CRIT = {
    # Zhang et al. 2018：s = v(2 - 2h/H)，H 取 2.5cm；动捕真值约 0.10 cm/frame
        # UE Layered Blend per Bone：additive 层不得污染下半身
    "lower_pollution":  (1e-9, "<", "UE Layered Blend per Bone: additive 只作用于 mask 覆盖骨，下半身零污染"),
    "box_rest_m":       (1e-9, "<", "放箱 detach 后 owner=world，箱体底面贴合台面（carry.box_release 契约）"),
"skate_cm_frame":   (1.0, "<", "Zhang et al.2018 foot skating s=v(2-2h/H), H=2.5cm; 动捕真值0.10cm/frame"),
    # ReinDiffuse：最低关节离地 >5cm 判 float
    "float_m":          (0.05, "<",
        "ReinDiffuse(arXiv:2410.07296, Han et al.) §Evaluation Metrics 原文: "
        "'Ground floating measures the distance between the ground and the lowest joint "
        "positions above the ground (> 5 cm)' —— 5cm 阈值出自该文正文，非自定"),
    # ReinDiffuse：双脚距离 <5cm 判 clip
    "feet_clip_m":      (0.05, ">",
        "ReinDiffuse(arXiv:2410.07296) §Evaluation Metrics 原文: "
        "'Foot clipping measures the distance between the left and right feet when it is "
        "less than a certain distance threshold (5 cm)' —— 5cm 阈值出自该文正文"),
    # 穿模容差：Box2D 官方默认 b2_linearSlop = 0.005 m
    # 出处：Box2D v2.4.1 源码 include/box2d/b2_common.h:65
    #       `#define b2_linearSlop (0.005f * b2_lengthUnitsPerMeter)`
    # 注意：此前误用 0.01（=官方 2 倍）并复制进 4 个判据，已按官方值统一修正。
    "penetration_m":    (_SLOP, "<",
        "穿模深度：Box2D 官方 b2_linearSlop=0.005m (v2.4.1 b2_common.h:65)；实测 C16 max=5.57e-4"),
    # 工程自测值：帧图灰度平均帧间绝对差（0~255）。
    # 注意：原引 SMPTE 属概念错用——SMPTE jitter 是广电时钟级概念(单位 UI/ps，
    # 见 SMPTE RP184 / ST 2059)，不存在"Jitter Score <0.1px"动画像素条款。
    "jitter_px":        (0.1, "<",
        "工程经验值(非SMPTE)：帧图灰度平均帧间绝对差；阈值由本工程自测标定"),
    # 骨段-球穿模：球心到骨段的最短距离 < 半径即穿模，容差同 _SLOP
    "seg_penetration_m": (_SLOP, "<",
        "骨段(胶囊)与球最短距离 < 半径即穿模；容差同 Box2D 官方 slop=0.005m"),
    # 帧间位移不得大于本帧应有位移的若干倍——抓时间跳变
    "frame_jump_ratio": (3.0, "<", "帧间位移/段内中位位移，比值过大即时间跳变"),
    # 长程漂移：WorldCycle（港科大&腾讯视频）RCS = 重复/级联执行时相位对齐帧漂移，
    # 长档 >381 帧；1mm 为动画可感知下限，故取 1e-3 m
    "pos_drift_m":      (1e-6, "<", "动机出处：WorldCycle/CycleBench（港科大·武大·腾讯视频AI技术中心, 2026-08）RCS=重复循环稳定性，长程档381帧。阈值非取自该文，为本工程自测标定：双精度1440帧累加9.7e-13留6量级余量，单精度1.7e-4会FAIL"),
    # 长程里程累积：辛积分（Velocity Verlet）误差有界振荡不漂移，显式欧拉才发散
    "mileage_rel_err":  (1e-9, "<", "GROMACS 辛积分：误差有界振荡不漂移；双精度实测2.9e-14留5量级余量，单精度5e-6会FAIL"),
    # 转角时序判据：jitter_px 是像素级(帧图灰度差)，用在角度序列上属口径错用，
    # 改用有实证上限的峰值角速度。
    "peak_rate_dps":    (460.0, "<",
        "【自测标定值，非取自文献】动机出处 Zago et al., ISBS 2015 Proceedings 33(1):1335-1338，"
        "但该文样本为 10 名 U-13 亚精英球员/29 次试验/5m 运球后脚底半转身，人群与任务均与原地转身错配；"
        "且公开渠道未能核实原文报告过 '414 (90) °/s' 骨盆峰值角速度，故不引用该数值。"
        "460 °/s 系本工程自测标定：实测转身峰值 399.6 °/s（裕度 13%）；"
        "定标顺序为 1020→460 收紧方向，非放宽（见 A1 铁律：阈值先定标再跑测试）"),
    # h_n = h_0 * e^(2n)，e = sqrt(h1/h0)
    "restitution_err":  (0.05, "<", "COR: e=sqrt(h1/h0), h_n=h_0*e^(2n)（UA PH125 实验手册）"),
    # 动量守恒相对误差
    "momentum_err":     (0.02, "<", "动量守恒 m1v1+m2v2 前后不变"),
    # 能量不得凭空增加（反弹越来越高）
    "energy_gain":      (1e-9, "<=", "物理不守恒：总能量不得增加(浮点容差 1e-9)"),
    # 肩→抓握中心：ARM 17.3 + FOREARM 15.5 + WRIST TO CENTRE OF GRIP 3.8 = 36.6% 身高
    # 另一独立来源（Dempster/Table 3.7）：0.1877+0.151+0.038 = 0.3767
    "arm_reach":        (0.377, "<", "Table M: ARM17.3+FOREARM15.5+WRIST-TO-GRIP3.8=36.6%H; Dempster 0.1877+0.151+0.038=0.3767H"),
    # 肘被动活动范围：过伸 5° → 屈曲 145°，超出即反折/超伸
    "elbow_reflex":     (0.0, "<=", "肘ROM 过伸5°~屈145°(Neumann/Kinesiology, Musculoskeletal Key)；实测=反折帧计数"),
    # 接触相浮空：跑步/跳跃触地相足底必须贴地
    "contact_float_m":       (_SLOP, "<",
        "接触相浮空：同 Box2D 官方 b2_linearSlop=0.005m (v2.4.1 b2_common.h:65)"),
    # 穿地：地面半空间穿透，容差同上
    "ground_penetration_m":  (_SLOP, "<",
        "穿地深度：同 Box2D 官方 b2_linearSlop=0.005m (v2.4.1 b2_common.h:65)"),
    # 抛体顶点高度 Δs = g·T_F²/8，相对误差 5%
    "flight_apex_err":       (0.05, "<", "抛体 Δs=g·T_F²/8(UA PH125 实验手册 Projectile Motion)，相对误差5%"),
    # 渲染剪影在 头顶→脚底 内的最长空行段（像素）。
    # 出处：Live 3D Human Reconstruction 用 2D Hausdorff 距离比对剪影，
    # 原文称其 "especially sensitive to holes and missing limbs"
    "flight_g_err":          (0.05, "<", "抛体轨迹二次拟合 a=-g/2(UA PH125 Projectile Motion 手册, 匀加速运动 y=y0+v0t-gt²/2)"),
    "silhouette_gap_px":     (2.0, "<", "2D Hausdorff between silhouette masks: sensitive to holes and missing limbs(Integrated Platform for Live 3D Human Reconstruction)"),
    # 渲染剪影纵向跨度 / 关节投影的头顶点—脚底点像素距离
    "silhouette_span_ratio": (0.90, ">", "同上：剪影须覆盖头到脚，比值过小即缺肢体"),
    # 渲染剪影 vs 胶囊几何真值掩膜的 IoU
    "mask_iou":              (0.75, ">",
        "IoU/Jaccard index（Jaccard P. 1912, New Phytologist 11:37-50, §相似度系数）；"
        "阈值 0.75 为本工程自测标定（实测 D22 剪影 IoU=0.9357 留 25% 余量）。"
        "撤除说明：原引 ResiHMR(arXiv:2604.28025) 主题为残肢人群单图 3D 人体网格恢复，"
        "与本判据无方法论关联，属语义贴牌，已撤除"),
  # 足端滑移（foot skating / sliding artifact）：支撑相足在世界系里的位移。
    # 业界判据：HumanML3D/CIMI4D 等文本生动作工作用 foot sliding metric 量化该伪影；
    # 阈值 1e-3 m 为本工程自测标定（爬梯/攀岩支撑相实测 ~1e-16 留 9 量级余量）。
    "foot_slip_m":          (1e-3, "<",
        "Foot skating/sliding artifact：支撑相足端世界位移（业界 foot sliding metric）；阈值本工程自测标定"),
    # Strouhal 数 St = f·A/v（A=尾端峰峰振幅）：生物高效巡航区间 0.2~0.4
    "strouhal_lo":          (0.2, ">", "Triantafyllou 1993：生物巡航 St 0.2~0.4（下界）"),
    "strouhal_hi":          (0.4, "<", "同上上界"),
    # 脊椎链段长守恒：PBD/Jakobsen 距离约束每次迭代后段长误差
    "seg_len_err":          (1e-6, "<",
        "Jakobsen 2001 Advanced Character Physics 距离约束：段长误差应收敛到 0"),
    # 三点支撑：攀岩/爬梯的稳定原则，任一时刻至少 3 个效应器固定
    "support_min":          (3, ">=", "攀岩三点支撑（three points of contact）：任一时刻 ≥3 效应器固定"),
    # 四足步态支撑足缺口：实测最少同时支撑足 vs 该步态期望值（GAIT_TABLE 第三项）
    "gait_contact_deficit": (0, "<=",
        "Hildebrand 1965 四足步态分类：walk/crawl 全程有支撑、trot/pace 对角 2 足、"
        "bound/gallop 存在腾空相(期望 0)；实测不得低于期望"),
    # ---- 以下 8 项由 tools/motionqual.py 测量（业界指标补齐，2026-10 新增）----
    # 只登记阈值与出处；测量实现不在本文件，避免"同一判据两套实现"
    "zmp_out_pct": (0.0, "<=",
        "ZMP 稳定性：ZMP 全序列落在支撑多边形（BoS）内则越界率 0；"
        "出处 HUMOS(arXiv:2409.03944) Dyn.Stability / BoSDist"),
    "bos_dist_m": (0.0, ">=",
        "同上：ZMP 到支撑多边形边界的最小距离（米），<0 表示越界"),
    "jitter_accel": (1e-3, "<",
        "Karunratanakul 2023 Jitter：关节加速度变化量均值，非像素级抖动；"
        "过大会表现为高频抽搐"),
    "pene_bone_m": (0.04, "<",
        "PeneBone(业界骨级自穿透指标)：每骨以 2cm 为半径做胶囊，"
        "非相邻骨间最深穿透深度；2r=0.04 即半径和的几何上界"),
    "contact_f1": (0.9, ">=",
        "CHOIS 接触指标：预测接触与真值接触的 precision/recall/F1；"
        "此处真值取动作自身声明的支撑相"),
    "duty_factor_err": (0.05, "<",
        "Hildebrand 1965 三变量之一：占空比(触地时长/周期)，"
        "walk 类应 >0.5；本项测实测与步态表期望值之差"),
    "phase_err": (0.05, "<",
        "同上：相对相位(以 LH 为参考的触地滞后)，"
        "trot 对角同相 0.0/0.5；本项测实测与期望之差"),
    "wave_len_ratio": (0.5, ">",
        "鱼类行波：体波波长/体长；鲹科巡航约 1 个体长量级，"
        "低于 0.5 说明行波未成形（出处 Triantafyllou 1993）"),
    # ---- 以下 4 项由 tests/cases_mixed.py 测量（H40 混合场景，2026-10 新增）----
    "nan_count": (0, "<=",
        "IEEE 754：NaN 参与任何算术均传播为 NaN，一旦出现即静默污染整条轨迹。"
        "混合场景里 NaN 的典型成因是子系统坐标口径不一致（如 2D 足端未补 z）"
        "或除零；阈值 0 表示零容忍"),
    "xbody_penetration_m": (_SLOP, "<",
        "跨实体穿模：与项目其余穿模判据同用 Box2D 官方 b2_linearSlop=0.005f"
        "(v2.4.1 b2_common.h:65)。不同实体的骨架定义不同，故用逐帧包围球"
        "（半径=该帧点集到质心的最大距离）比较，不逐骨段互比"),
    "min_arc_m": (0.01, ">",
        "防「实体没接上时间轴」：总弧长而非首尾距离——圆周/往复运动首尾距离"
        "可为 0，用首尾距会把原地摆动误判成静止。3 秒 72 帧下完全静止为 0，"
        "0.01m 足以区分静止与真实微幅运动（绳末端 Verlet 收敛后残余摆动）"),
    "time_span_err_s": (1.0 / 24, "<=",
        "时间轴同步：各实体覆盖时长之差不得超过一帧(24fps=0.0417s)。"
        "超过一帧即出现某些实体先结束/后开始的错位，"
        "与多轨合成的帧对齐要求一致"),
    # ---- 以下 8 项由 motion/phenom.py 测量（常见物理现象，2026-10 新增）----
    "leaf_v_term_mps": (3.13, "<",
        "树叶飘落终端速度上限取 0.5·√(2gh)（h=2m）：flutter 的终端速度必须"
        "显著低于同高度自由落体，否则说明阻力未起作用。"
        "实测 flutter 0.1645 m/s、tumbling 0.5533 m/s"
        "(出处 Wang & Pesavento 2004 PRL; Andersen et al. 2005 JFM)"),
    "frac_max_disp_m": (1.0, "<",
        "碎块飞散位移上限：超限说明断裂释放的能量数值爆炸（PBD bond 失效瞬间"
        "位置投影过冲）。实测 0.4961 m"),
    "water_spread_ratio": (1.0, ">",
        "水柱冲击地面后横向铺展比（终态横向范围/初始横向范围）。"
        "小于 1 说明流体被约束成柱子、密度约束未求解，"
        "等于 1 说明粒子没动（出处 PBF Macklin & Müller 2013）"),
    "water_rho_rel": (0.10, "<",
        "PBF 不可压缩：静息后平均 |ρ/ρ0-1|。密度约束求解达标即应收敛到"
        "静息密度附近，实测 0.0145（1.45%）"),
    "cradle_th_mid_win_rad": (0.03, "<",
        "牛顿摆中间球在首次碰撞后 0.25s 窗口内的最大角位移，取 0.05·θ0"
        "(θ0=0.60rad)。等质量弹性碰撞⇒速度交换、中间球保持静止，"
        "这是牛顿摆的可观测签名（出处 GAUGE arXiv:2608.05948）"),
    "cradle_th_last_win_rad": (0.30, ">",
        "同窗口内末球最大角位移，取 0.5·θ0：末球应被弹到接近首球初始摆角"),
    "turntable_r_end_m": (0.10, ">",
        "转台物块最终半径需大于初始半径 r0=0.10：离心力 mω²r 超过静摩擦锥"
        "μs·m·g 后必然向外滑移（ω=8rad/s 时 mω²r=6.4N > μs·m·g=3.43N）"),
    "turntable_lateral_m": (1e-6, ">",
        "科氏力 -2mω×v_rel 产生横向偏转，区别于纯径向离心："
        "无科氏项时横向位移恒为 0，故 1e-6 足以自证该项已生效"),
    "leaf_drift_m": (1e-4, ">",
        "flutter 必须有水平漂移：纯竖直下落说明升力项未起作用。"
        "实测 3.54 m（2m 落差下的滑翔）"),
    "leaf_swings": (2.0, ">=",
        "flutter 的定义是左右摆动滑翔（swing≥2 次），"
        "区别于直线下坠（出处 Andersen et al. 2005 JFM 双稳态分类）"),
    "frac_n_broken": (1.0, ">=",
        "墙被撞后必须有 bond 超过 strain_limit 而失效，否则等于没裂"),
    "frac_n_frag": (2.0, ">=",
        "裂开的定义是连通分量 >1（出现独立碎块）；等于 1 说明只是整体位移"),
    "water_n_alive": (162.0, ">",
        "PBF 粒子数守恒：出现 NaN 或逃逸流体即丢失质量，存活粒子须 >90%·180。"
        "不用 ==：浮点相等在边界吸收粒子时会脆断，且 mutate 变异体无法区分"
        "'全存活'与'少一个'，== 判据没有牙齿（注：judge() 不支持 ==，"
        "历史上此处登记 == 会让 P43 直接抛 ValueError）。"
        "注意判有限须逐粒子取 axis=1，漏 axis 会退化成标量而恒过"),
    "cradle_energy_err": (0.05, "<",
        "牛顿摆能量守恒：e=0.999 允许少量耗散，实测 0.0241。"
        "单摆积分用 dt=1/4000 保证摆本身不引入显著漂移"),
}
