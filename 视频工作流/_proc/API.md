# API 手册（自动生成）

> 由 `gen_api.py` 从契约块与 `@capability` 装饰器抽取，**改代码后需重跑**。
> 人工编辑会在下次生成时被覆盖；要长期保留的说明请写进各文件的契约块。

## 一、能力索引（52 项）

能力名可直接喂给 `beat.Timeline`；出处写在 `source` 参数里，空出处需先补再调用。

### carry（2）

| 能力 | 出处 | 落点 |
|---|---|---|
| `box_release` | 放箱：半蹲降至箱底接触台面后 detach（owner=world），与 prop.Handoff 的 release/recovery 同构 | `motion/character/carry.py:351` |
| `carry_box` | 半蹲举 膝~90°/躯干~45°（Burgess-Limerick & Straker 2003）；箱体约束到躯干骨（Animation Master）；NIOSH RWL=LC× | `motion/character/carry.py:238` |

### character（2）

| 能力 | 出处 | 落点 |
|---|---|---|
| `fish_strouhal` | Triantafyllou 1993：巡航最优 St≈0.25，生物区间 0.2~0.4 | `motion/creature/fish_swim.py:111` |
| `fish_swim` | Videler & Hess 行波 y(x,t)=Am(x)cos(2π/λ(x−ct))；Tytell carangiform 包络 a0=1,a1=−3.2,a2=5.6 | `motion/creature/fish_swim.py:81` |

### grasp（1）

| 能力 | 出处 | 落点 |
|---|---|---|
| `reach_grab` | Fitts 定律 ID=log2(2A/W)；两骨 IK 伸向目标 | `motion/character/crouch.py:170` |

### interact（4）

| 能力 | 出处 | 落点 |
|---|---|---|
| `contact` | 胶囊接触分离按质量反比平分；静态障碍由 agent 全额承担（Box2D 静态质量定义） | `motion/crowd.py:314` |
| `crowd_collide` | ORCA 互避 + 接触分离；最近接近点解析解 t*=(p·v_rel)//v_rel/²，tc=min(t*,τ) | `motion/crowd.py:320` |
| `high5` | 击掌：上臂外展至 90°水平、掌心相对拍合（Utween ECA 低层序列） | `motion/crowd.py:326` |
| `multi_actor` | ORCA 互避（van den Berg 2011 §3.2）；多主体统一推进，同时选速后一并积分以消除顺序偏差 | `motion/crowd.py:308` |

### interaction（1）

| 能力 | 出处 | 落点 |
|---|---|---|
| `pass_ball` | **缺出处** | `motion/character/pass_ball.py:201` |

### locomotion（5）

| 能力 | 出处 | 落点 |
|---|---|---|
| `brake` | Graham-Smith sprint-to-stop DTS 2.39m; Harper 制动姿态:降COM/脚前置/躯干直立略后倾 | `motion/character/run.py:241` |
| `jump` | 弹道 Δs=g·T_F²/8（UA PH125 抛体运动） | `motion/character/jump.py:163` |
| `kick` | 近端到远端顺序(Dorge 1999); 足质量分数0.0145(Winter 1990) | `motion/character/kick.py:203` |
| `quadruped` | Hildebrand 1965 Symmetrical gaits of horses (duty factor β + footfall phase); CPG gait tab | `motion/creature/quadruped.py:82` |
| `run` | Novacheck 1998 / Minetti-Alexander 1997 (β=0.35); GI 1996 步长回归 sl=0.1394+0.00465v | `motion/character/run.py:234` |

### motion（2）

| 能力 | 出处 | 落点 |
|---|---|---|
| `box` | Box2D v2.4.1 b2_linearSlop=0.005; Coulomb friction sliding | `motion/character/push.py:74` |
| `push` | Box2D v2.4.1 b2_linearSlop=0.005; sequential impulse contact | `motion/character/push.py:37` |

### navigate（1）

| 能力 | 出处 | 落点 |
|---|---|---|
| `walk` | **缺出处** | `motion/beat.py:298` |

### phenom（6）

| 能力 | 出处 | 落点 |
|---|---|---|
| `fracture` | GAUGE(arXiv:2608.05948) Wall Breaking; 内聚区断裂(Dugdale 1960/Barenblatt 1962) | `motion/phenom/fracture.py:207` |
| `leaf_fall` | Wang & Pesavento 2004 PRL; Andersen/Pesavento/Wang 2005 JFM: 升力∝v·ω耦合项 | `motion/phenom/leaf.py:28` |
| `leaf_fall` | Andersen et al. 2005 JFM 薄片下落双稳态(flutter/tumbling) 准稳态气动模型 | `motion/phenom/leaf.py:73` |
| `newton_cradle` | GAUGE(arXiv:2608.05948) Newton's Cradle; 等质量弹性碰撞⇒速度交换 | `motion/phenom/cradle.py:52` |
| `turntable` | GAUGE(arXiv:2608.05948) Turntable; 非惯性系离心力mω²r与科氏力-2mω×v | `motion/phenom/turntable.py:28` |
| `water_jet` | Position Based Fluids(Macklin & Müller 2013); SPH 2D 核归一化 | `motion/phenom/water.py:28` |

### phys（4）

| 能力 | 出处 | 落点 |
|---|---|---|
| `hinge_door` | PBD point-coincidence constraint (rest=0); parallel-axis theorem I=I_c+m·d² | `motion/constraint_ext.py:91` |
| `roll` | Halliday/Resnick Fundamentals of Physics §11: rolling without slipping v=ω·r; energy conse | `motion/character/roll.py:43` |
| `rope` | Jakobsen 2001 Advanced Character Physics (Verlet + distance constraint relaxation); Müller | `motion/constraint_ext.py:48` |
| `toppling` | rigid body statics: tipping when CoM passes support edge; emergent in World solver | `motion/constraint_ext.py:122` |

### physics（10）

| 能力 | 出处 | 落点 |
|---|---|---|
| `bounce` | COR: e=sqrt(h1/h0), h_n=h_0·e^(2n)（UA PH105 LeClair / Purdue ME274） | `motion/rigid.py:162` |
| `broadphase` | 均匀网格空间哈希（Teschner et al. 2003）；fat AABB + padding（Box2D b2DynamicTree） | `motion/physics_ext.py:186` |
| `ccd` | Box2D v3 speculative contacts + TOI(b2TimeOfImpact)；保守推进子步（单步位移 ≤ K_FRAC·r） | `motion/physics_ext.py:139` |
| `friction` | 库仑摩擦锥 /f_t/ ≤ μ·f_n（Box2D b2Friction / Box2D Lite k_friction） | `motion/physics_ext.py:283` |
| `gravity_off` | 无外力 ⇒ 动量守恒 dp/dt=0，质心匀速直线（牛顿第一定律） | `motion/physics_ext.py:248` |
| `overlap_resolve` | Baumgarte 位置修正 + linear slop 0.005（Box2D v2.4.1 b2_common.h:65 官方实测）；max linear correction | `motion/physics_ext.py:319` |
| `pendulum` | 距离约束冲量法(=Box2D b2DistanceJoint)；最低点撞击水平方向动量守恒 | `motion/rigid2d/sim.py:88` |
| `ramp` | 斜面滚动：a=g(sinθ-μcosθ)；圆-顶点接触+顺序冲量 | `motion/rigid2d/sim.py:59` |
| `rigid_body` | 半隐式/Verlet定步长积分 + 冲量法碰撞响应（Erin Catto GDC2011 / Box2D） | `motion/rigid.py:190` |
| `stack` | 顺序冲量+warm starting+Baumgarte(Erin Catto GDC2006/Box2D Lite) | `motion/rigid2d/sim.py:33` |

### posture（1）

| 能力 | 出处 | 落点 |
|---|---|---|
| `crouch` | 深蹲膝~124°/髋~124°（Cursa / Kinetech 解剖） | `motion/character/crouch.py:165` |

### prop（3）

| 能力 | 出处 | 落点 |
|---|---|---|
| `ball` | 球规格(IFAB Law 2); 恢复系数 h_n=ε^{2n}h_0(UA PH125) | `motion/character/kick.py:209` |
| `catch` | 预测拦截+最小急动度5次多项式(Flash&Hogan 1985; TUM Minimum Jerk for Human Catching Movements in 3D) | `motion/character/catch.py:164` |
| `throw` | 动力链顺序(Fleisig et al.1996 Sports Medicine DOI 10.2165/00007256-199621060-00004); 抛体 R=u²sin | `motion/character/throw.py:303` |

### 未分类（10）

| 能力 | 出处 | 落点 |
|---|---|---|
| `bird_fly` | Wu & Popović 2003; Nudds et al. 2004; Pennycuick 1996; Sane & Dickinson | `motion/creature/bird_fly.py:203` |
| `carry_prop` | **缺出处** | `motion/character/prop.py:469` |
| `climb` | **缺出处** | `motion/character/climb.py:63` |
| `climb_rock` | **缺出处** | `motion/creature/climb_rock.py:129` |
| `finger_tap` | **缺出处** | `motion/character/gesture.py:122` |
| `gaze_shift` | **缺出处** | `motion/character/gesture.py:80` |
| `page_flip` | **缺出处** | `motion/character/gesture.py:211` |
| `prop_release` | **缺出处** | `motion/character/prop.py:475` |
| `turn` | **缺出处** | `motion/character/turn.py:359` |
| `wave` | **缺出处** | `motion/character/gesture.py:168` |

## 二、模块公开面（115 个模块）

只列顶层公开函数（下划线开头为内部实现，不承诺稳定）。

### `_canary_faultbench.py`

缺陷注入基准的对照样本，注入前必须全绿

- `area(r)`　`L14`　—　圆面积：S = pi * r^2。
- `circumference(r)`　`L19`　—　圆周长：C = 2 * pi * r。
- `ratio(a, b)`　`L24`　—　比值，b 为 0 时返回 None 而非抛异常。
- `total(xs)`　`L31`　—　对序列求和。
- `mean(xs)`　`L41`　—　算术平均，空列表返回 None。
- `clamp(v, lo, hi)`　`L48`　—　把 v 限制在 [lo, hi] 区间内。
- `self_check()`　`L57`　—　自检：返回 (名称, 是否通过) 列表。

### `base/assertrun.py`

统一断言执行器——各模块 self_check 改写为"计算抽 helper + 数据表 chk"

- `run(mod, fn=True, verbose)`　`L112`　—　跑一个模块的 self_check 并兜住异常（异常判 FAIL，不静默通过）。

### `check.py`

（缺一句话职责）

- `walk_py()`　`L78`
- `pkg_of(path)`　`L86`
- `node_of(path)`　`L91`　—　节点名 pkg.module，用于传递依赖分析。
- `edges(path)`　`L99`　—　返回该文件 import 到的 (pkg, module) 节点集合。
- `main()`　`L457`　—　编排：建依赖图 → 逐文件扫描 → 包粒度汇总 → 出报告。

### `color/paint.py`

按胶囊 region 查色卡，配合 SDF 法线做明暗着色；颜色挂 region 不挂像素

- `hex2rgb(h)`　`L57`
- `ramp(name, n=5)`　`L62`　—　取一条色阶 → RGB 数组 (n,3)，从暗到亮。
- `skin_rgb(fitz, idx)`　`L70`　—　按 Fitzpatrick 型取肤色 RGB。
- `shade(d, ramp_rgb, light, amb, rim_pow, rim_amt=(-0.55, -0.62, 0.56), d_max=0.42)`　`L76`　—　inflate 伪 3D：由 SDF 直接算法线，再把法线亮度映射到 ramp 的哪一级。
- `paint_regions(d, region_masks=None, palette, light)`　`L115`　—　按 region 分区着色。

### `formula.py`

公式注册表与 STUB 门禁：缺公式抛错并给搜索关键词，禁止凭记忆写近似值

- `load()`　`L23`
- `index(reg)`　`L28`
- `require(fid, reg=None)`　`L37`　—　取公式描述。IMPL/MIGRATE 返回；其余一律抛错。
- `check(ids)`　`L53`　—　批量声明。返回 (可用, 缺口清单)
- `panel()`　`L65`
- `audit_source(reg)`　`L98`　—　工具优先（用户定）：标 IMPL 的公式必须带 source（文献/出处/URL）。
- `claim(fid, source=None, reg)`　`L112`　—　把搜到的出处写回登记表，并把状态置为 IMPL。

### `gen_api.py`

从契约块与能力装饰器自动生成 API.md，补齐"只有契约块、无接口文档"的缺口

- `iter_py()`　`L39`　—　遍历 _proc 下全部 .py，返回排序后的绝对路径列表（铁律5：结果不依赖遍历顺序）。
- `one_liner(path)`　`L50`　—　取文件头部契约块的一句话职责；取不到返回占位串，不静默跳过。
- `rel(path)`　`L60`
- `scan_capabilities(path, text)`　`L64`　—　用 AST 抽 @capability 装饰器：能力名、source、group。
- `scan_public_funcs(path, text)`　`L106`　—　抽顶层公开函数签名（不含下划线开头），只取名字与参数，不取函数体。
- `build()`　`L139`　—　扫全部文件，返回 (能力列表, 模块列表)。
- `by_group(caps)`　`L157`
- `render(caps, mods)`　`L164`
- `main()`　`L194`

### `gen_index.py`

从各文件顶部契约块抽取职责，自动生成 INDEX.md（文档永不与代码脱节）

- `one_liner(path, text=None)`　`L38`　—　只从文件头 40 行抽取职责，避免抓到源码里的正则片段。
- `scan_tree()`　`L69`　—　扫描三层目录，返回 {层名: [(文件名, 行数, 一句话职责)]}。
- `main()`　`L112`　—　编排：扫描 → 头部 → 三层树 → 规则表 → 问题清单 → 写盘。

### `jumpscan.py`

（缺一句话职责）

- `scan(path, max_frames=1200)`　`L13`

### `motion/beat.py`

节拍时间线：prep→stroke→relax 三相位串多段动作，含跨段无跳变与互斥校验

- `capability(name, source='other', group)`　`L74`
- `require(name)`　`L84`　—　缺能力就炸，并给出该去搜什么。绝不静默返回近似动作。

### `motion/camera.py`

相机：视高/焦距/px_per_m(Z)/反投影；人物与路必须共用同一台

- `fit(geom, cam_h, fov_h_deg, f=1.6)`　`L105`　—　从背景 geom 反解相机。

### `motion/capbridge.py`

能力表分类归一 —— 姿态/增量/物理/辅助四类分流，并把非标准签名适配成 (u,params)

- `normalize(cap, cap_src=True, cap_group, verbose)`　`L208`　—　就地归一化：四类分流，能适配成 POSE 的适配后归入 POSE。返回分类字典。
- `add_pose(base, delta=1.0, weight)`　`L236`　—　增量叠加：base + delta*weight（UE additive / layer.py 同语义）。

### `motion/character/ball.py`

（缺一句话职责）

- `strike_mass(body_mass)`　`L31`　—　有效击球质量: 足(含鞋) ≈ 84% → M = m_foot / 0.84
- `impact(v_foot, n, m_eff, m_ball=None, e=M_BALL)`　`L36`　—　脚-球一维碰撞(球初始静止)。
- `flight(p0, v0, t)`　`L52`　—　解析抛物线, t 可为数组 → 位置 (N,2) 米
- `bounce_series(h0, e, n=E_GROUND)`　`L61`　—　落地反弹峰高序列: h_k = ε^{2k}·h_0
- `trajectory(p0, v0=E_GROUND, t_end, dt, e)`　`L66`　—　带反弹的轨迹(逐段解析)。返回 (T, P): 时刻与位置数组。
- `self_check()`　`L97`

### `motion/character/body/cloth.py`

布料：Verlet 链、披帛/衣摆、draw_character 总入口

- `make_robe(attach, height_px)`　`L62`　—　衣摆 / 飘带链：锚点在腰与胸，长度按身高比例，不是拍脑袋的像素数。
- `draw_character(cv, ctx, t, preset, phase0, x, y, height_px, robe, skin, attach, chains, wind, dt, yaw=0.0, body_h='natural')`　`L88`　—　人物表（2D）入口：正交相机 + 侧视。沿路走远请直接用 draw_body + 真相机。

### `motion/character/body/gait.py`

步态主函数：臂摆、膝屈曲线、相位推进与 BODY_SPEC

- `solve_root(ph, P, step)`　`L67`　—　根：侧向摆 + 重心起伏 + 双脚世界锁定。
- `solve_legs(root, stance)`　`L100`　—　腿：脚世界锁定 + 两骨 IK 反求膝盖（消除打滑）。
- `solve_spine(ph, P, root)`　`L135`　—　脊柱：S 曲线 + 反向旋转（髋摆 → 胸反相）。
- `solve_arms(ph, P, spine)`　`L158`　—　臂：肩反相于同侧髋。
- `gait(ph, preset, scale_h, stride, stance='natural')`　`L182`　—　步态求解：相位 ph∈[0,1) → 每个关节的 **(u, v, w)**（归一化身高单位）

### `motion/character/body/joints.py`

关节表、躯干摆动常量、步态预设与 gait_params

- `joint_angle(joint, ph)`　`L9`　—　实测关节角关键点 → 线性插值出任意相位的角度（弧度）。
- `gait_params(preset, body_h)`　`L87`　—　由文献公式推出该预设的全部时间/幅度量。

### `motion/character/body/leg.py`

腿：两骨 IK、踝高曲线、脚掌俯仰与脚部关键点

- `two_bone_ik(root, target, L1=(1.0, 0.0), L2=None, bend, prev)`　`L21`　—　两骨 IK 解析解（余弦定理）—— 走路脚锁定的核心。
- `ahead_for_com(leg_reach, ank_h_n, com_drop_n)`　`L72`　—　触地瞬间脚落在重心前方的距离（归一化身高）——由实测 COM 垂直降幅反解。
- `ankle_h_curve(phs)`　`L94`　—　外踝离地高度（归一化身高）。直接插值实测表，不手填系数。
- `foot_local(phs, stride, stance, lift, ank_h, step_len=0.828)`　`L108`　—　脚踝相对身体中心的位置。phs=0 为刚着地。
- `foot_pitch(phs, stance=0.62)`　`L158`　—　脚掌绝对俯仰角（rad，正=脚尖朝上）。查表+线性插值，首尾闭合，绝不外推。

### `motion/character/body/proportions.py`

人体比例常数（Drillis&Contini 1966）与步频/步态常量

- `arm_reach(shoulder, grip=1.7, H)`　`L81`　—　肩→抓握中心 距离 / 身高。超出 ARM_REACH_MAX(0.377) 说明手臂被拉长。

### `motion/character/body/render.py`

渲染：相机投影、SDF 场栅格化、法线明暗着色

- `project_body(J, cam, Xc, Zc, yaw=0.0, body_h=10.0)`　`L17`　—　归一化 (u,v,w) 关节 → 屏幕像素。
- `body_geometry(Jp, body_h=1.7)`　`L41`　—　屏幕关节 → 胶囊表（像素）。半径按各自深度的 像素/米 缩放。
- `field_px(caps, ell=6.0, smooth, pad)`　`L62`　—　在**屏幕像素网格**上建 SDF。返回 (d, (x0, y0), d_head)。
- `draw_body(cv, cam, J, Xc, Zc, yaw, body_h, robe, skin, chains, wind, dt=0.0, attach=10.0, hem_scale=90.0)`　`L131`　—　统一渲染入口：任何相机 / 任何朝向 / 任何深度都用这一条。
- `shade_sdf(d, base_rgb, light, amb, rim_pow, rim_amt=(-0.55, -0.62, 0.56), d_max=0.42)`　`L164`　—　由 SDF 直接算伪 3D 法线并着色。

### `motion/character/body/sdf.py`

SDF 场原语（胶囊/圆/椭圆/平滑并集）+ BODY_SPEC 胶囊装配清单

- `sd_capsule(px, py, ax, ay, bx, by, r)`　`L13`　—　胶囊 SDF。px,py 可以是数组。负=内部
- `sd_circle(px, py, cx, cy, r)`　`L23`
- `sd_ellipse(px, py, cx, cy, rx, ry)`　`L28`　—　近似椭圆 SDF（精确解要解五次方程，此处用缩放近似，够用）
- `smin(a, b=0.0, k)`　`L35`　—　多项式平滑并集（polynomial smooth min）

### `motion/character/carry.py`

（缺一句话职责）

- `semi_squat(q)`　`L84`　—　半蹲姿态 q=0 站 / q=1 半蹲（膝~90°、躯干~45°），双脚不动。
- `box_pose(J, size=BOX)`　`L112`　—　箱体位姿：约束到躯干（chest）前方，背面贴住身体（NIOSH H 最小化）。
- `hug_arms(J, box=1.0, blend)`　`L135`　—　双手环抱箱体两侧：手心在箱侧面外 WRIST_TO_GRIP（不穿透）。
- `sphere_box_pen(sphere_c, sphere_r, box_c, box_half)`　`L176`　—　球心到 AABB 最近点距离 → 穿透深度（负值=分离）。
- `carry_box(u, params=None)`　`L238`　—　全程进度 u∈[0,1] → {'phase','owner','J','box'}。
- `box_release(J, surface_v=BOX, size)`　`L351`　—　放下：返回箱体最终位姿（底面贴合 surface_v）。

### `motion/character/catch.py`

（缺一句话职责）

- `ball_flight(t_phys)`　`L46`　—　来球(米): 解析抛物线, t_phys 单位秒
- `intercept_point()`　`L53`　—　预测拦截点 IP(米): 球在 T_MOVE 时刻的位置(预测策略)
- `hand_center(t)`　`L93`　—　手心(米): 等于 _hand_rel 所给目标(拦截点/回收位), 精确无残差
- `ball_center(t)`　`L100`　—　球心(米): 接触前按弹道, 接触后停住并随手
- `catch(t)`　`L109`　—　接球: 返回关节字典(归一化身高)
- `self_check()`　`L124`

### `motion/character/climb.py`

爬梯：五效应器三态循环上升，肘膝由两骨IK反解保证骨长守恒

- `climb(t, rung_sep, body_h, cycle, base=0.3)`　`L63`　—　爬梯姿态。
- `self_check()`　`L198`　—　爬梯自检：连续性、骨长守恒、不超伸、无 NaN、周期闭合。

### `motion/character/crouch.py`

（缺一句话职责）

- `crouch(q, with_arms=True)`　`L60`
- `reach_pose(q, obj_u, obj_v, obj_r, arm=OBJ_U)`　`L92`　—　下蹲 + 手臂两骨 IK 伸向物体（肩固定、肘向后弯）
- `self_check()`　`L127`

### `motion/character/gesture.py`

注视转移 / 手指敲击 / 翻页 —— 头部与手部的短促动作

- `eye_velocity(a_min_deg, v0=GAZE_V0)`　`L64`　—　注视峰值速度 V_MAX = (2/75·A_MIN + 1/6)·V0 —— Pejsa 2016 式(1)。
- `gaze_shift(u, params=None)`　`L80`　—　转移注视：眼先动 → 头追上 → VOR 锁定。
- `tap_envelope(u, spans=TAP_SPANS)`　`L111`　—　Lango 三段包络：anticipation 抬 → strike 落 → settle 回。返回 (值, 段名)。
- `finger_tap(u, params=None)`　`L122`　—　手指敲击：手腕上下，部件依次滞后（手指最晚）。
- `wave_envelope(u)`　`L157`　—　挥手包络：返回 (抬起进度, 摆动值)。抬起 smoothstep，摆动正弦。
- `wave(u, params=None)`　`L168`　—　挥手：抬右臂 → 手掌左右摆动，肩肘腕联动。
- `page_flip(u, params=None)`　`L211`　—　翻页：手带过书页中线，纸张绕书脊镜像。params: side(right/left) amp
- `page_curl(u)`　`L231`　—　书页变形量：返回 (x_scale, y_lift)。x 从 1 镜像到 -1，y 起半圆弧。
- `page_shadow(u)`　`L237`　—　翻页阴影强度：中途（u≈0.5，页垂直）最深，两端为 0。
- `self_check()`　`L306`

### `motion/character/jump.py`

（缺一句话职责）

- `hip_h_jump(t)`　`L57`
- `jump(t, scale_h=1.0)`　`L88`
- `self_check()`　`L131`

### `motion/character/kick.py`

（缺一句话职责）

- `contact_point(t)`　`L87`　—　脚背触球点(米), 2D: (水平, 竖直)
- `foot_vel(t, dt=1e-05)`　`L93`　—　触球点速度(米每秒), 后向差分
- `ball_center(t)`　`L104`　—　球心(米): 触球前静止于地面, 触球后按碰撞结果飞行
- `kick(t, scale_h=1.0)`　`L119`
- `self_check()`　`L159`

### `motion/character/pass_ball.py`

（缺一句话职责）

- `flight1(tt)`　`L105`　—　第一程（A→B）：tt 为出手后秒数
- `flight2(tt)`　`L110`　—　第二程（B→A）：tt 为出手后秒数
- `release_vel1()`　`L115`
- `release_vel2()`　`L119`
- `pose_A(t)`　`L124`　—　A（左侧，面朝 +X）：投 → 站立等待 → 接
- `pose_B(t)`　`L135`　—　B（右侧，面朝 -X）：站立等待 → 接 → 缓冲 → 投回
- `held_by(t)`　`L149`　—　球此刻在谁手里（None 表示飞行中）
- `hand_world(t)`　`L163`　—　持球者的手心世界坐标（米）
- `ball_world(t)`　`L179`　—　球心世界坐标（米）
- `self_check()`　`L249`　—　对传自检：判据不变，断言交统一执行器。

### `motion/character/prop.py`

道具交接 —— pickup→held→release→recovery 四相位，所有权 world↔hand 显式切换

- `phase_of(u, spans=SPANS)`　`L55`　—　归一化进度 u∈[0,1] → 相位名。u 已被调用方保证在 [0,1]。
- `ease_target(a, b, t)`　`L68`　—　smoothstep 缓动：3t²−2t³。出处 FrameSprite（手接近/回位均需缓动，忌线性）。
- `pivot_offset(size)`　`L76`　—　pivot(底面中心) → 几何中心的偏移（归一化身高）。
- `grip_offset(size, side='right')`　`L86`　—　抓取点相对手腕的偏移（归一化身高）：手在道具侧面中上部。
- `world_to_body(P, Xc=1.7, Zc, yaw, body_h)`　`L101`　—　世界 (X,Y,Z) → 身体 (u,v,w)。手要抓地上的杯子，就得先把它换算到身体坐标。
- `body_to_world(p, Xc=1.7, Zc, yaw, body_h)`　`L112`　—　身体 (u,v,w) → 世界 (X,Y,Z)。world_to_body 的逆。
- `grab_point_world(prop, Xc=None, Zc, yaw, side)`　`L121`　—　抓取时手腕应在的世界位置（米）。
- `grab_target(prop, Xc, Zc=1.7, yaw=None, body_h, side)`　`L139`　—　抓取目标（身体坐标，归一化身高）：手腕该伸到哪里。
- `drop_point_world(prop, surface_h=None, Xc, Zc, yaw, side)`　`L145`　—　放下时道具底面中心该落在的世界位置：给定台面高度，贴着台面放。
- `can_transfer(J, body_h, threshold=1.7)`　`L153`　—　双手是否进入交接区（米）。出处 PropHandoff(Blender)：
- `transfer(prop, to_side, require_zone, J, body_h='right')`　`L164`　—　换手：owner 从一只手切到另一只手。
- `reach_arm(J, side=1.7, target, body_h)`　`L184`　—　两骨 IK 解手臂：肩→目标，出肘与腕。复用 leg.two_bone_ik（余弦定理解析解）。
- `clamp_arm(J, side=REACH_FRAC, frac)`　`L209`　—　把任一来源（gait/sit/gesture）给出的肩→腕距离收进臂展球面，并重解肘。
- `draw_prop(cv, cam, prop=None, anchor_px=None, s)`　`L316`　—　画道具（立方体线框+面）。anchor_px 给定时用它（握持中），否则世界投影。

### `motion/character/push.py`

推动箱体（B12）：掌为运动学驱动，箱受地面摩擦与接触约束

- `push_sim(push_v, t_end, hw, hh, mass, mu)`　`L37`　—　掌（运动学）水平推箱，箱受地面摩擦。
- `box_sim(mu, v0, t_end, hw, hh, mass)`　`L74`　—　箱体自由滑行：给初速后由库仑摩擦减速至停（验证摩擦与穿模）。
- `self_check()`　`L97`

### `motion/character/roll.py`

纯滚动（E25/球体滚动）：无滑移约束 v=ω·r + 能量守恒

- `roll_sim(theta_deg, L, mu, T, dt, r, mass)`　`L43`　—　圆盘沿斜面纯滚落。
- `self_check()`　`L87`

### `motion/character/run.py`

（缺一句话职责）

- `step_len(v, H=1.7)`　`L71`　—　步幅(m)。v: m/s。sl = (0.1394 + 0.00465·v_min)·sqrt(H/1.8)。
- `step_freq(v, H=1.7)`　`L79`　—　步频(步/秒)。v = sl·sf → sf = v/sl。
- `trunk_lean(v)`　`L85`　—　躯干前倾角(度)。慢跑 3°，冲刺 15°，线性插值。
- `run(ph, v, H=3.2)`　`L175`　—　跑步步态。ph: 步相 0~1（单腿周期）。返回归一化关节字典。
- `brake(t, v0, D, H=3.2)`　`L209`　—　急停。返回 {'v':当前速度, 'd':已行距离, 'u':进度, 'J':关节}。
- `self_check()`　`L245`

### `motion/character/sit.py`

坐下/站起动作 —— 7 关键姿态 + 三相位，输出与 gait 同构的关节字典

- `solve_hip(seg, sub, e)`　`L113`　—　髋高 / 前后位移 / 躯干前倾 —— 三相位查表（Cursa 7 关键姿态 + MDPI 实测角）。
- `solve_legs(hip_uv)`　`L149`　—　腿与脚 —— 脚先锁定，膝由两骨 IK 反求（膝弯多少是几何后果，不手填）。
- `solve_spine(hip, lag, seg)`　`L169`　—　脊柱堆叠 —— lean 是角度，位移 = 倾角 × 力臂；胸/头滞后于髋（Cursa 第④条）。
- `solve_arms(hip, seg, sub, e, shoulder_v, chest_u)`　`L186`　—　臂 —— 坐下时向后撑（髋后移的反相），站起时前摆；周期起止回到自然下垂。
- `sit_pose(p, preset='natural')`　`L225`　—　坐下/站起主函数 —— 返回与 gait 同构的关节字典（Composed Method 顶层）。
- `contact_frames(fps)`　`L245`　—　返回 (触椅帧, 离椅帧) —— 坐下动作段结束即触椅，站起段开始即离椅。
- `com_u(p)`　`L251`　—　近似 CoM 前后位置：躯干四点平均（含头前伸 —— 坐下时头前伸正是平衡髋后移的关键）。
- `support_polygon_u(seg)`　`L257`　—　支撑多边形前后范围：站定=双脚；坐下全过程与坐姿=脚∪椅。

### `motion/character/throw.py`

（缺一句话职责）

- `hand_center(t, prev=None)`　`L120`　—　手心(米): 腕 + 抓握偏移(沿前臂方向)
- `release_vel(dt)`　`L131`　—　出手速度(米每秒): 释放前一瞬手速, 后向差分(与 kick.foot_vel 同口径)
- `ball_center(t)`　`L146`　—　球心(米): 释放前被握住(随手), 释放后解析抛物线
- `throw(t, prev_el=None)`　`L192`　—　投掷: 返回关节字典(归一化身高)
- `self_check()`　`L291`　—　投掷自检：判据不变，断言交统一执行器。

### `motion/character/turn.py`

yaw 连续转身 + 原地换步 —— 让人物真的"转过去"而不是镜像翻转

- `turn_profile(s)`　`L100`　—　主转段内角度比例 r(s)：s∈[0,1] → r∈[0,1]，非对称。
- `turn_speed(delta_deg)`　`L117`　—　转身角速度 °/s。|Δ|≤100° 用基础速率，越大越快，180° 到上限。
- `turn_duration(delta_deg)`　`L126`　—　转身耗时（秒）——取"分档速率"与"峰值角速度约束"两者的较大值。
- `turn_yaw(yaw0, delta_deg, u)`　`L150`　—　进度 u∈[0,1] → 当前 yaw。三段不对称时间曲线。
- `turn_stance(u)`　`L188`　—　换步状态：左右脚抬起高度 + 屈膝量。
- `turn_legs(J, u)`　`L204`　—　把换步施加到腿部关节（业界: 转身动画只带腿部动作，朝向由每帧 yaw 定）。
- `turn_torso(J, u, delta_deg)`　`L228`　—　分段转向：躯干滞后于骨盆、头部最后跟上。
- `self_check()`　`L342`　—　转身自检：判据与改造前逐条一致，计算抽 helper、断言交统一执行器。

### `motion/constraint_ext.py`

约束扩展三能力：rope / hinge_door / toppling

- `rope_sim(n, seg, anchor, iters, steps)`　`L48`　—　绳子：顶端锚定的 Verlet 链 + 距离约束。
- `hinge_door_sim(w, h, mass, torque, t_end)`　`L91`　—　门绕铰链转动：点重合约束锁铰链，力矩驱动角加速度。
- `toppling_sim(hw, hh, push, t_end)`　`L122`　—　推倒竖块：水平冲量使质心越过支撑棱后自动翻转（求解器涌现，非手工判定）。
- `self_check()`　`L146`　—　自检：三约束各自的物理不变量（数据表化，执行器统一跑）。

### `motion/creature/bird_aero.py`

鸟翼气动与翼骨几何的纯函数真源（自 bird_fly 拆出，供其导入）

- `stroke_angle_deg(b)`　`L62`　—　翼展相关的扑翼行程角（Nudds 2004：θ ≈ 67·b^(−0.24)，度）。
- `flapping_angle(t, f, amp_deg, b=None, down_frac=1.2)`　`L72`　—　扑动角 φ(t)（弧度，+ 为上举）。
- `is_downstroke(t, f=DOWN_FRAC, down_frac)`　`L90`　—　相位是否处于下扑段（dφ/dt<0）。
- `flapping_rate(t, f, amp_deg, b=None, down_frac=1.2)`　`L95`　—　dφ/dt（弧度/秒），解析导数，供叶素法求局部气流速度。
- `fold_factor(t, f, fold=FOLD, down_frac=DOWN_FRAC)`　`L106`　—　翼折叠因子 eff ∈ [fold, 1]：下扑完全伸展(1)，上举屈曲回收(fold)。
- `sweep_angle(t, f, sweep_deg=12.0, down_frac=DOWN_FRAC)`　`L122`　—　仰角/扫掠角 θ(t)（弧度，+ 为前掠）。
- `wing_aero(t, f, U, b, S, alpha0_deg=RHO_AIR, rho=DOWN_FRAC, down_frac=FOLD, fold=None, amp_deg=N_ELEM, n_elem)`　`L162`　—　准定常叶素法：对双侧翼沿展向积分，返回 (Fx, Fy)（牛）。
- `trim_alpha(f, U, b, S, m=RHO_AIR, rho=-5.0, lo=25.0, hi=60, iters)`　`L200`　—　反解配平攻角 α0：使一个翼拍周期内的平均升力 = m·g（定常水平飞行）。

### `motion/creature/bird_fly.py`

鸟飞扑翼：三位置角 + 下扑/上举不对称 + 准定常叶素法气动（升力/推力由积分真算）

- `beat_freq_pennycuick(m, b=RHO_AIR, S, rho)`　`L72`　—　Pennycuick 扑翼频率律 f = m^(3/8) g^(1/2) b^(−23/24) S^(−1/3) ρ^(−3/8)。
- `stroke_amplitude(b)`　`L81`　—　扑动振幅 A（米，翼尖峰峰值的半幅）A = b·sin(θ/2)，θ=67b^(−0.24)。
- `strouhal(f, b, U)`　`L86`　—　St = f·A/U，A=b·sin(θ/2)。巡航高推进效率区间 0.2~0.4。
- `cruise_speed(f, b=ST_DIRECT, St)`　`L91`　—　由 St 反解巡航速度 U = f·A/St。与鱼游同款 Strouhal 反解。
- `bird_flight_sim(m, b, S, U, alpha0_deg, alt0, t_end, dt, rho, down_frac, fold)`　`L99`　—　前向动力学积分：m·ÿ = ΣF_y − m·g，机体竖直起伏由此**算出**。
- `bird_fly(t, m, b, S, U, alt0, t_end, body_len, down_frac, fold, sweep_deg=1.0)`　`L154`　—　单帧鸟骨架（世界坐标米制）。高度取自配平仿真的周期稳态解。
- `self_check()`　`L210`　—　飞行自检：分四组（频率巡航 / 骨长守恒 / 气动因果 / 帧间采样）。

### `motion/creature/climb_rock.py`

不规则支点攀岩：环境查询支点 + 两骨 IK 放置 + 三点支撑

- `wall_holds(n_level, dy, base_y, jx)`　`L58`　—　生成岩壁支点集（环境）。
- `sweep_hold(pos, holds, reach, min_rise=0.45, up=0.05)`　`L74`　—　环境查询：球形范围扫掠 + 法线点乘判坡度。
- `climb_rock(t, cycle, dy, base_y, body_h=1.6)`　`L129`　—　攀岩姿态。
- `self_check()`　`L234`　—　攀岩判据自检：环境查询 / 三点支撑 / 骨长守恒 / 不穿壁 / 平滑 / 上升。

### `motion/creature/fish_swim.py`

鱼游行波推进：等弧长脊椎链 + carangiform/anguilliform 包络 + St 反解

- `fish_swim(t, body_len, freq, speed, tail_amp, mode, n_seg=0.3)`　`L81`　—　鱼体行波游动。tail_amp 为尾端单边振幅（米），默认取 St=0.25 反解。
- `fish_strouhal(freq, tail_amp, speed)`　`L111`　—　Strouhal 数 St = f·A/v，A 取尾端峰峰振幅（2×单边振幅）。
- `self_check()`　`L179`

### `motion/creature/quadruped.py`

四足步态——Hildebrand 占空比β+四足相位表参数化，支撑相足端零滑移

- `quadruped_sim(cycles, n, gait, speed, freq, world)`　`L82`　—　四足步态：生成四足端轨迹、躯干高度、触地相位与支撑标志。
- `foot_slip(feet, support)`　`L131`　—　业界滑移指标：支撑相足端在世界系的最大帧间位移(m)。
- `self_check()`　`L149`

### `motion/crowd.py`

多主体：ORCA 互避 + 胶囊接触分离 + 击掌时序

- `closest_approach(a, b=TAU, tau)`　`L63`　—　最近接近点解析解 → (t*, 最近距离, 该时刻由A指向B的单位向量) 或 None
- `ttc(a, b=TAU, tau)`　`L93`　—　预期碰撞时间（秒），不碰撞给 τ·2 上界（出处[3] 惩罚项要用）
- `orca_plane(a, b=TAU, tau)`　`L102`　—　ORCA 半平面 → (n, point_A, point_B)
- `orca_velocity(agent, others, vmax, tau=1.4, w=TAU)`　`L134`　—　给单个 agent 选一个满足所有 ORCA 半平面、且最接近期望速度的速度
- `orca_step(agents, dt, vmax=1.4, tau=TAU)`　`L178`　—　推进一帧：先各自选速，再统一积分（避免顺序偏差）
- `contact_depth(a, b)`　`L188`　—　重叠深度（米）；不重叠为 0
- `resolve_contact(a, b=1.0, static_gain)`　`L194`　—　位置分离：按质量反比平分推开，胶囊不旋转（出处[4]）
- `separate_all(agents, iters=4)`　`L218`　—　迭代分离所有重叠对（出处[5] Unity CapsuleCast 的『迭代解析』）
- `crowd_sim(agents, t_end, dt, vmax=1.0 / 24.0, tau=1.4)`　`L237`　—　人群推进：每帧 ORCA 选速 + 积分 + 接触分离。
- `high5_arm(t, t_contact, duration, H=1.2, side=1.7)`　`L262`　—　击掌右臂抬升曲线 → (肩外展角°, 肘屈角°, 腕高/身高)
- `high5_pose(t, t_contact, gap=1.7, H=1.2, duration)`　`L287`　—　两人击掌 → (腕A, 腕B, 掌心距)，腕坐标在『两人连线』局部系
- `self_check()`　`L383`　—　群体自检：判据不变，断言交统一执行器。

### `motion/layer.py`

（缺一句话职责）

- `bone_w(joint, region=1.0, layer_w)`　`L57`　—　单骨骼最终权重 = Mask 权重 × LayerWeight（Unity：两者相乘）
- `blend(base, over, region, mode='full', layer_w='override')`　`L80`　—　合成一位姿
- `compose(base_fn, overlays, t)`　`L103`　—　声明式入口：只写意图，不手算参数
- `solve_min_jerk(p0, p1, T)`　`L117`　—　最小急动度 5 次多项式系数（Flash & Hogan 1985）
- `min_jerk_at(coef, t)`　`L131`　—　按 solve_min_jerk 的系数取 t 时刻位置（自动满足 C2 连续）
- `solve_ballistic(p0, tgt, v0=None, g=9.80665)`　`L138`　—　反解抛体初速：给定出手点、目标点，自动算该用多快
- `attach(obj_xyz, pose=(0.0, 0.0, 0.0), joint, offset)`　`L161`　—　物体自动跟随骨骼：给关节名即可，不手算世界坐标
- `self_check()`　`L226`　—　分层自检：判据不变，断言交统一执行器。

### `motion/phenom/cradle.py`

常见物理现象能力族（leaf_fall/fracture/water_jet/newton_cradle/turntable）

- `newton_cradle_sim(n, L, r, m, th0, T, dt, e)`　`L52`　—　牛顿摆：首球拉起释放，等质量弹性碰撞 ⇒ 末球弹出、中间球静止。

### `motion/phenom/fracture.py`

砖墙被球撞击碎裂（内聚区 bond 应变阈值失效）

- `fracture_sim(cols, rows, brick, gap, mass, strain_limit, ball_m, ball_r, v0, T, dt, iters, restitution, damping)`　`L207`　—　砖墙被球撞击碎裂：bond 拉伸超临界应变即失效（内聚区断裂）。

### `motion/phenom/leaf.py`

常见物理现象能力族（leaf_fall/fracture/water_jet/newton_cradle/turntable）

- `leaf_fall_sim(L, h, m, rho_f, T, dt, theta0, I_scale, ground_y, w0, spin)`　`L73`　—　薄片（树叶/纸片）飘落：flutter（摆动滑翔）与 tumbling（持续翻滚）。

### `motion/phenom/turntable.py`

常见物理现象能力族（leaf_fall/fracture/water_jet/newton_cradle/turntable）

- `turntable_sim(om_p, r0, mu_s, mu_k, m, T, dt)`　`L28`　—　旋转平台上的物块：离心力超过静摩擦锥后向外滑移。

### `motion/phenom/water.py`

常见物理现象能力族（leaf_fall/fracture/water_jet/newton_cradle/turntable）

- `water_jet_sim(nx, ny, d, rho0, T, dt, iters, jet_v, seed, eps, mass_k, max_step_k, gf)`　`L28`　—　水流冲击地面：PBF 密度约束求解，落地后横向铺展。

### `motion/physics_ext.py`

物理扩展五能力：ccd/broadphase/gravity_off/friction/overlap_resolve

- `body_radius(b)`　`L63`　—　体的外接半径：圆取 r，盒取对角半长 hypot(hw,hh)。
- `pen_vs_plane(b, plane_y=0.0)`　`L73`　—　刚体对水平面 y=plane_y 的**几何精确**穿透深度（支撑函数）。
- `pen_vs_plane_max(bodies, plane_y=0.0)`　`L92`　—　对所有动态体取 pen_vs_plane 的最大值。
- `substeps_for(bodies, dt, k_frac=K_FRAC, barrier=None)`　`L108`　—　保守推进所需子步数 N：使单子步位移不超过屏障。
- `ccd_sim(v0, wall_x, wall_hw, r, T, dt, ccd)`　`L139`　—　高速球撞薄墙：ccd=False 会隧穿，ccd=True 被挡住。
- `broadphase_sim(n, T, dt, seed)`　`L186`　—　50 球同时落地互撞：统计宽相候选对、暴力对、漏检数与最大穿透。
- `gravity_off_sim(v0, T, dt)`　`L248`　—　零重力漂浮：球匀速直线，撞静止球后总动量守恒。
- `friction_sim(mu, v0, T, dt)`　`L283`　—　高摩擦滑动：滑块初速 v0 在地面滑行，应迅速停止且不反弹。
- `overlap_resolve_sim(n, r, T, dt, seed)`　`L319`　—　初始重叠：一批球起点互相重叠，应被推开到 slop 内且不闪烁。
- `self_check()`　`L361`　—　自检：五能力各自的物理不变量（数据表化，执行器统一跑）。

### `motion/rigid.py`

刚体物理：半隐式欧拉定步长积分 + 冲量法碰撞响应 + 恢复系数衰减

- `integrate(b, dt=G, g)`　`L73`　—　Velocity Verlet 一步（出处[1] 的辛族积分器）
- `collide_ground(b, ground, g=0.0)`　`L88`　—　地面碰撞：由本步末速度反推真实撞击速度，再施加 COR（出处[4]）
- `collide_pair(a, b)`　`L107`　—　球-球冲量响应（出处[3]）。沿质心连线法线，1D 情形 n=±1
- `simulate(bodies, t_end, dt, g, ground=FIXED_DT, pairs=G)`　`L137`　—　定步长推进，返回 (轨迹 list[list[float]], 最大穿透)
- `bounce_traj(h0, e, t_end, dt=FIXED_DT, g=G, r=0.11)`　`L162`　—　弹球：从 h0 静止下落，返回 (高度序列, 峰值序列)
- `bounce_peaks_theory(h0, e, n_bounce)`　`L183`　—　理论峰值 h_n = h_0·e^(2n)（出处[4]），用于比对
- `two_ball(m1, m2=1.0, v1, v2, e)`　`L190`　—　一维对撞后速度（出处[3] 冲量公式的闭式解）
- `register(cap, src, group)`　`L203`　—　由 motion.beat 注入装饰器，避免本模块 import beat（防环）
- `self_check()`　`L215`

### `motion/rigid2d/collide.py`

碰撞检测：SAT 盒-盒、地面、圆-线段（含参考面裁剪）

- `collide_box_box_np(A, B)`　`L59`　—　OBB-OBB 接触流形：SAT 选轴 + 顶点包含法（出处[3] Box2D）。
- `collide_box_box(A, B)`　`L100`　—　OBB-OBB 接触流形：SAT 选轴 + 顶点包含法（出处[3] Box2D）。
- `collide_ground(b, gy, n=0.0)`　`L218`　—　半空间 y >= gy：所有低于平面的支撑点（出处[3] 顶点法）
- `collide_seg(body, seg)`　`L340`　—　物体 vs 静态线段。返回 [(接触点, 法线A→B, 穿透)]

### `motion/rigid2d/core.py`

2D 刚体常量（Box2D 原文值）与几何基元（Body2/旋转/叉积）

- `rot(th)`　`L37`
- `cross(a, b)`　`L42`
- `cross_w(w, r)`　`L46`　—　角速度叉乘半径 → 线速度增量

### `motion/rigid2d/sim.py`

场景仿真：stack/ramp/pendulum 三个能力 + self_check

- `stack_sim(n_box, size, T, dt)`　`L33`　—　方块堆叠：静置求稳定。返回 (世界, 每帧最大穿透, 质心轨迹)
- `ramp_sim(theta_deg, L, mu, T, dt)`　`L59`　—　球沿斜面滚下。返回 (球, 轨迹[(x,y)], 最大穿透, 理论加速度)
- `pendulum_sim(L, th0_deg, T, dt, m1, m2, with_traj)`　`L88`　—　摆锤从 th0 摆下，最低点撞击静止球。返回 (摆, 球, 碰撞前后水平动量, 最大穿透)
- `self_check()`　`L129`

### `motion/rigid2d/solve.py`

接触求解：Contact 预处理、冲量施加、顺序冲量迭代、距离约束

- `solve(contacts, dt=ITER, iterations)`　`L67`　—　顺序冲量求解（出处[1]）：warm start → 迭代法向+摩擦

### `motion/run.py`

时间线与出片：逐帧渲染并写 mp4

- `draw_actor(cv, cam, J, Xc, Zc, yaw, body_h, template, hand_lod, palette, front, stroke=0.0, stroke_w=10.0, hand_curl=90.0)`　`L133`　—　画一个角色：线 + 色，全部挂在胶囊上。
- `frame(t, scene, geom, bg, yaw, lane, Z0, speed, phase0, preset, body_h, template, palette, w, h, cam=None)`　`L163`　—　一帧 = 时间的纯函数。任意 t 可单独渲染，帧间不携带状态。
- `to_mp4(frames, path=30, fps)`　`L186`　—　短片用：frames 为已驻留内存的 PIL 图列表。

### `motion/stage.py`

场景合成：烘焙背景 + 人物 + 出片

- `bake(scene_name, biome=kit.BIOME_A)`　`L34`　—　烘焙静态背景，返回 (PIL.Image, geom)。geom 含 horizon/vanish 供人物对齐。
- `placement(geom, depth, body_h, cam=0.3)`　`L44`　—　人物站位与身高 —— 由相机算，不再手填系数。
- `render_seq(scene_name, n, fps, preset, depth, wind, phase0, preload)`　`L62`　—　渲染 n 帧，返回 (frames, geom)。
- `step_len(preset, body_h)`　`L96`　—　一步的米数 —— 由骨架反推，并与文献公式交叉校验。
- `walk_seq(scene_name, n, fps, preset, speed, stride_m, Z0, lane, yaw, body_h, wind, preload, phase0)`　`L204`　—　沿路真正走远：世界坐标驱动，透视相机投影（Composed Method）。
- `to_mp4(frames, path=30, fps)`　`L240`
- `sheet(frames, cols, pad, bg=6)`　`L250`　—　把帧排成一张索引图。

### `motion/wind.py`

风场：主弯曲 + 细节弯曲，相位纳入世界坐标使异株不同步

- `triangle_wave(x)`　`L34`　—　GPU Gems 3 Ch.16 原文逐字：abs(frac(x + 0.5) * 2.0 - 1.0) → [0,1]，周期 1。
- `smooth_triangle_wave(x)`　`L42`　—　SmoothTriangleWave = SmoothCurve(TriangleWave(x))。
- `main_bend(z_norm, wind_xy=1.0, bend_scale)`　`L54`　—　主弯曲位移。z_norm=归一化高度（根0→顶1）。
- `detail_phase(world_xyz, branch_phase=0.0)`　`L67`　—　相位纳入世界坐标（原文 fObjPhase = dot(worldPos.xyz, 1)）。
- `detail_bend(t, world_xyz, speed, detail_freq, edge_amp, branch_amp, n_xy=1.0, branch_phase=1.0)`　`L76`　—　细节弯曲。返回 (dx, dy, dz)，前两项是边缘摆动，第三项沿法向上下。
- `sway(t, world_xyz, wind_xy, z_norm, bend_scale, speed, detail_freq, edge_amp, branch_amp=1.0, n_xy=1.0, branch_phase=1.0)`　`L90`　—　主弯曲 + 细节弯曲的合成 —— 树/草/旗统一走这个函数，共享同一个风场。

### `prompt2spec.py`

提示词 → 规格对照：逐字段判能做/降级/不能，STUB 带搜索提示

- `check(verbose)`　`L126`　—　逐字段问引擎。STUB 走 formula.require 抛错（不静默降级）。
- `stats(rows)`　`L144`
- `by_module(rows)`　`L156`
- `register_stubs(stubs)`　`L175`　—　把缺的登记进 FORMULA_REGISTRY —— 后续按 search_hint 逐个搜，一次只搜一个。

### `scene/bgpack.py`

背景包：五种配方的参数表与展开，输出 geom 供人物对齐

- `biome_color(h, table=BIOME_A)`　`L62`　—　高度 → 颜色，离散色带（不做渐变混合，保留插画感）
- `sky_lum(theta, gamma=2.5, theta_s, T)`　`L99`　—　返回相对天顶亮度 Y/Yz ∈ [0, ~1]
- `horizon_sky_rgb(theta_s, T, warm, cool=2.5)`　`L122`　—　地平线附近的天空色。低太阳角→暖，高→冷（Rayleigh 散射）。
- `fbm1d(rng, n, octaves, persistence, lacunarity=5, base_freq=0.5)`　`L146`　—　分形噪声。业界标准：
- `ridge(rng, k, roughness, amp=8)`　`L161`
- `ramp(c0, c1=NONUNIFORM_STOPS, t, stops)`　`L179`　—　非等距色标渐变。业界：等距四分之一读起来像 CSS，
- `list_presets()`　`L211`
- `draw_sky(px, horizon_y, P, fog, zenith)`　`L224`　—　天空：Preetham 亮度分布 × 非等距渐变（天顶比地平线暗）。
- `draw_ground(px, horizon_y, h, P)`　`L233`　—　地面：近处暗、远处并入基色（与空气透视同向）。
- `draw_ridges(d, horizon_y, h, w, P, fog, rng)`　`L241`　—　远山：midpoint displacement，逐层向【雾色】靠拢（雾色即天空色，故天然一致）。
- `draw_road(d, horizon_y, h, w, vanish_x, P, fog)`　`L267`　—　路面：三角形收敛到消失点。返回路面几何（供人物/元件共享）。
- `draw_wall(d, horizon_y, h, w, vanish_x, P)`　`L285`　—　城墙：两侧沿透视曲线收向消失点。返回墙几何或 None。
- `make_veg(rng, horizon_y, h, w, P)`　`L307`　—　植被锚点：L-B 可动部件（树/草/旗）的位置，本步只标位置不画。
- `render(preset, w, h, seed, horizon_ratio)`　`L316`　—　背景包渲染（Composed Method 顶层）—— 只讲"先画什么、再画什么"的故事。
- `self_check()`　`L430`　—　逐组自检：断言分组，多失败一起报，不停在第一个。

### `scene/detail.py`

近处细节：草叶/窗户/叶簇/远处行人，按 LOD 分级

- `lod_at(ctx, y)`　`L71`　—　屏幕 y → LOD 级。0=最细（画面底部），3=最粗（贴地平线）。
- `jittered_pts(rng, x0, x1, y0, y1, cols, rows)`　`L103`　—　抖动网格（jittered grid）——蓝噪声的廉价近似。
- `grass_row(ctx, w=1.0, h, hy, r, rows, density)`　`L151`　—　计算第 r 个深度带的几何与 LOD 参数。
- `grass_fade(fog, fog_t)`　`L169`　—　按空气透视把基色/尖色/枯色向雾色靠拢。返回 (cb, ct, cd)。
- `draw_grass_far(cv, rng, row, w, gb, ban_fn)`　`L176`　—　最远带：单株不足 1px，只画密集色点，不画形。
- `draw_blade(cv, rng, gx, gy, lod, blade_h, cb, ct, scale)`　`L188`　—　单株草：LOD0 完整弯曲叶片 / LOD1 三叶簇 / LOD2 单线段。
- `draw_grass(cv, ctx, density, seed=1.0, dry=11)`　`L205`　—　草被（Composed Method 顶层）—— 按深度带从远到近铺，带越远株越小越少。
- `draw_flowers(cv, ctx, density=1.0, seed=13)`　`L295`　—　野花。近处花瓣+花心，中距彩点，远处并入草色不单独画。
- `draw_crowd(cv, ctx, n=8, seed=17)`　`L320`　—　远处行人：impostor 级 LOD。
- `facade_windows(d, x0, x1, y_top, y_bot, rng, style, palette, lod, fog_t, fog)`　`L409`　—　沿 x 切分出门窗（Split Shape Grammar 的最小形态），仅做编排。
- `canopy(d, cx=14, cy_top, cy_bot, rx, ry, rng, lod, fog_t, fog, n)`　`L438`　—　树冠叶簇：多个椭圆团 + 明暗梯度，替代"一个实心椭圆"。
- `self_check()`　`L468`

### `scene/kit/canvas.py`

Canvas 画布 + 噪声基元（value noise / fBm / smoothstep）

- `value_noise2(w, h=0.0, freq, seed)`　`L46`　—　2D value noise，返回 (h,w) ∈ [0,1]
- `fbm2(w, h, octaves, freq, seed, lacunarity=4, persistence=5.0)`　`L62`
- `smoothstep(a, b, x)`　`L73`

### `scene/kit/city.py`

城：多排矩形坡顶房屋，越近越大越暗

- `draw_city(cv, ctx, n, rows, seed=14, style=2)`　`L13`　—　房屋。多排：越近越大越暗（透视）。

### `scene/kit/compose.py`

场景组合：元件注册表、配方表、compose 总入口

- `draw_grass(cv, ctx)`　`L16`
- `draw_flowers(cv, ctx)`　`L20`
- `draw_crowd(cv, ctx)`　`L24`
- `list_elements()`　`L42`
- `compose(scene, w, h, horizon_ratio, biome=540)`　`L48`　—　scene: {"name":..., "layers":[{"t":"sky",...}, ...]}  从远到近

### `scene/kit/indoor.py`

室内一点透视：房间壳几何、投影 proj()、水磨石地面

- `make_geom(w, h, preset='咖啡馆', seed=7)`　`L37`　—　房间几何。与 camera.fit 契约一致（horizon_y/vanish_x/road_half_near）
- `proj(g, X, Y, Z)`　`L54`　—　世界坐标 → 屏幕。地面 Y=0：y = v_h + f*eye/Z（与 Cam.ground_y 同式）
- `draw_shell(cv, g)`　`L66`　—　地板/天花/左右侧墙/后墙。一点透视：VP 向画框四角连线
- `draw_floor(cv, g=7, seed)`　`L88`　—　水磨石地面：彩点散布 r=r_min*(1+noise)，越远越小越淡（空气透视）
- `render(w, h, preset='咖啡馆', seed=7)`　`L108`

### `scene/kit/props.py`

室内陈设：落地窗/书架墙/挂画/家具，输出世界坐标锚点供人物就位

- `draw_window(cv, g, z0, z1, y0, y1=1.2, seed=5.4)`　`L22`　—　左墙落地窗：竖梃沿 Z 均分，透视上间距递减
- `draw_bookshelf(cv, g, z0, z1, y0, y1, rows=1.2, seed=5.6)`　`L39`　—　右墙书架：层板 + 书籍，越远越暗（空气透视）
- `draw_photos(cv, g=3, n)`　`L67`　—　后墙三幅黑白摄影（提示词明确要求）
- `draw_props(cv, g)`　`L95`　—　高脚椅 / 矮桌 / 沙发，并把世界锚点写进 geom 供人物就位

### `scene/kit/road.py`

路面半宽、禁用区间、路面绘制与避让裁剪

- `road_hw(ctx, y=0.0, margin)`　`L16`　—　路面在屏幕 y 处的半宽。所有元件共用同一条路的几何。
- `road_ban(ctx, y=0.0, margin)`　`L30`　—　路面在 y 处的禁用区间 [x0,x1]。返回 None 表示此处无路。
- `draw_road(cv, ctx, half_near=0.26, expo=1.0)`　`L52`　—　路。先写 ctx['road_p'] 让后续元件能避让——哪怕路这层后画也行。

### `scene/kit/selfcheck.py`

自检：python -m kit.selfcheck

- `self_check()`　`L93`　—　逐组自检：断言分组，多失败一起报，不停在第一个。

### `scene/kit/sky.py`

天空：Perez 天光模型、地平线色、色带 ramp

- `draw_sky(cv, ctx, theta_s=0.9, T=2.8)`　`L13`　—　Preetham/Perez 解析亮度 × 非等距色标渐变
- `horizon_rgb(theta_s, T, warm, cool=2.5)`　`L65`
- `draw_cloud(cv, ctx, coverage, scale=0.35, seed=5.0)`　`L88`　—　stacked Perlin fBm + smoothstep 阈值

### `scene/kit/terrain.py`

地形：山脊 midpoint displacement、地面、色带

- `draw_mountain(cv, ctx, layers, rough, amp=4, seed=0.62)`　`L12`　—　多层 midpoint displacement 山脊 + 等高色带，逐层并入雾色。
- `draw_ground(cv, ctx)`　`L60`
- `biome_color(hv, table=BIOME_A)`　`L80`

### `scene/kit/tree.py`

树：Honda 1971 三参数分形（分叉角/长度比/深度）

- `draw_tree(cv, ctx, x, ybase, height, kind, jitter=None, seed=None)`　`L46`　—　单棵树。分形递归，三参数决定整棵剪影（Honda 1971）。
- `draw_trees(cv, ctx, n, kind, seed=6, band='槐')`　`L90`

### `shape/hand.py`

手部解剖：掌与五指的关节/胶囊，按真实比例与外展角生成

- `hand_pose(wri, elb, side, hand_len, splay, curl='r', palm_frac=HAND_LEN)`　`L75`　—　由腕与前臂方向推出整只手的关节（归一化坐标，×身高）。
- `attach(J, hand_lod, curl, hand_len, splay=1)`　`L111`　—　把两只手挂到姿态 J 上，返回新 dict（不改动入参）。
- `caps(lod, s='skin', region)`　`L129`　—　手的胶囊表 [(a, b, r, region)]，r 为归一化半径（×身高）。
- `joints(lod, s)`　`L154`　—　该 LOD 需要的关节名（用于模板登记）。

### `shape/line.py`

骨架模板 → 胶囊形体(带 region) → SDF → 轮廓线与细节线

- `HAND_LOD(lod, s='skin', region)`　`L75`
- `build_body(template, hand_lod, body_h)`　`L102`　—　返回 (关节名表, 胶囊表[(a,b,r,region)], 末端脚表)。
- `sd_capsule(px, py, ax, ay, bx, by, r)`　`L118`
- `sd_ellipse(px, py, cx, cy, rx, ry)`　`L126`
- `smin(a, b=0.0, k)`　`L131`
- `field(caps_ell, pad, smooth=6.0)`　`L139`　—　caps_ell = (胶囊表[(ax,ay,bx,by,r)], 头椭圆表[(cx,cy,rx,ry)])
- `outline(d, w=1.6)`　`L168`　—　轮廓线 = SDF 的天然副产品：abs(d) - w。一行数学，不用几何外扩。
- `detail_lines(d, density, w=120.0)`　`L174`　—　内部等高线（衣纹/发纹/肌理）。density 就是线密度，可调。
- `stroke_mask(d, w, inner=1.6)`　`L179`　—　轮廓 + 内部等高线，合成描边蒙版。
- `face_points(head_xy, head_r, yaw=90.0, front=False)`　`L187`　—　五官锚点 → 屏幕坐标。挂在头骨局部，头一转五官跟着转。
- `draw_face(cv, pts, ink, front=(40, 30, 26), w=False)`　`L199`　—　寥寥几笔画出眼鼻嘴耳。

### `showreel/cafe.py`

咖啡馆 12 秒时间线：四段动作（坐姿→抬头→起身走→落座沙发）

- `pose_at(t)`　`L130`
- `frame(t, bg, cam, palette)`　`L158`
- `main()`　`L178`

### `showreel/camrig.py`

连续相机运镜（跟随/横移/推拉/低角度/俯拍/微距），全程 C1 连续不切镜

- `default_shots()`　`L121`　—　90 秒默认运镜表（对应需求各段）。
- `self_check()`　`L162`

### `showreel/params.py`

全局物理参数的连续扰动曲线（重力/摩擦/风/弹性/质量/时间缩放）

- `smoothstep(a, b, x)`　`L35`　—　[2] C1 连续过渡，端点导数为 0。
- `catmull_rom(p0, p1, p2, p3, t)`　`L44`　—　[1] 标准 Catmull-Rom（uniform, α=0），C1 连续。
- `spline_at(keys, t)`　`L54`　—　keys: [(t, v), ...] 按 t 升序。C1 连续穿过所有关键帧。
- `self_check()`　`L243`　—　自检：连续性 + 值域 + 可复现性（判据不变，断言交统一执行器）。

### `showreel/phys.py`

90秒物理预跑，轨迹存 npz、状态 pickle 成 checkpoint 续跑

- `run(start, end, chunk)`　`L134`
- `main()`　`L176`

### `showreel/render.py`

分层合成——背景/远雨/物体/角色/近雨/辉光，复用既有管线不自造

- `build_bg(seed)`　`L130`　—　雨夜街道底板：天空渐变、建筑剪影、霓虹招牌、湿沥青与倒影。
- `add_rain(img, t=0.0, wind)`　`L167`　—　三层雨：远(细暗慢) / 中 / 近(粗亮快)。雨丝随风向倾斜。
- `draw_props(dr, cam=Z_PROP, props, Z)`　`L181`　—　按深度排序画场景物体。props: 每项 (x, y, th, hw, hh, kind, col)。
- `props_from_world(bodies, snap, i=None)`　`L203`　—　由物理 world.bodies（或回放快照）→ props 列表。
- `post(img, t)`　`L223`　—　霓虹辉光（亮部提取→模糊→叠加）+ 暗角。
- `compose(t, cam, bg, props, actors=None, wind=None, rain=0.0)`　`L240`　—　合成一帧。actors: [(Xc, Zc, yaw, J, palette, body_h)]。

### `showreel/scene.py`

90 秒场景世界——多米诺/方块堆/斜坡/摆锤/墙/梯子/移动靶/绳/铰链门

- `domino_pitch(half_h, half_s)`　`L40`　—　骨牌间距 = 2×半高（≈一倍骨牌高），出处[1]。
- `topple_angle(half_s, half_h)`　`L51`　—　临界倾倒角 θ_c = arcsin(s/h)（出处[1]）。
- `make_dominoes(world, n, x0, half_h, half_s, mu=20)`　`L60`
- `make_stack(world, n, x0, half, mu, tag=6)`　`L75`　—　规则堆叠（底部宽、逐层收窄更稳）。
- `make_wall(world, x0, cols, rows, half, mu=13.0)`　`L87`　—　砖墙：可推倒。返回 body 列表。
- `make_ramp(world, x0, y0, dx, dy, mu=8.0)`　`L104`
- `make_ladder(world, x, y0, h, n, half_w=11.5)`　`L110`　—　梯子：两侧立柱 + n 根横杆（静态，爬梯用）。
- `make_pendulum(world, anchor, L, th0_deg, m=(9.5, 2.6))`　`L125`　—　单摆：DistanceConstraint 铰接（锚点固定）。
- `make_rope(world, a, b, n, m=(4.0, 1.6))`　`L179`　—　PBD 绳：n 个质点 + 相邻距离约束（出处[2]）。
- `make_hinge_door(world, hinge, w, h, m=(6.5, 0.0))`　`L200`　—　铰链门：门板质心 + 到铰链的距离约束（门绕铰链转）。
- `self_check()`　`L380`　—　街景自检：判据不变，断言交统一执行器。

### `showreel/seam.py`

段内跳帧与段间接缝的流式检测，不全帧入内存

- `scan_file(path, w=W)`　`L34`　—　流式扫单文件: 返回 (首帧, 末帧, 段内差数组)。
- `main(argv)`　`L70`

### `showreel/shard.py`

90秒长镜头分段渲染落盘再 concat，规避内存与时限

- `main(argv)`　`L129`

### `showreel/timeline.py`

按视频帧查表渲染，背景/物体/角色/雨丝，相机不切镜

- `load_traj()`　`L37`　—　读所有 traj_*.npz → 段列表 [(F, n, 3), ...]。
- `snap_at(segs, i)`　`L52`　—　按全局帧号取该段的快照（每段物体数可能不同）。
- `load_meta()`　`L62`　—　重建 Street 拿几何元信息（顺序与轨迹一致）。
- `background(draw, t, cam_s, cam_x, y0)`　`L76`　—　夜空渐变 + 霓虹楼影 + 湿沥青（自绘，不依赖 kit）。
- `draw_bodies(draw, meta, frame, cam_s, cam_x, y0)`　`L117`　—　正交投影画物理物体：sx = cx + (X-cam_x)*s, sy = y0 - Y*s。
- `rain(draw, t, rng)`　`L148`　—　雨丝：固定种子，随时间下落，避免逐帧随机闪烁。
- `pose_woman(t)`　`L161`　—　女性姿态合成（0-24s 段）。
- `render(start, end, w, h, out)`　`L188`　—　90秒长镜头主循环：物理轨迹查表 + 连续相机 + 分层合成。
- `main(argv)`　`L238`

### `tests/cases.py`

（缺一句话职责）

- `seed_of(cid)`　`L143`
- `rng(cid)`　`L150`

### `tests/cases_base.py`

（缺一句话职责）

- `case_A1()`　`L9`　—　直线行走：滑步 / 浮空 / 双脚互穿 / 时间连续性
- `case_A2()`　`L99`　—　跑步急停：跑 2 个完整步周期 → 匀减速急停至 0
- `case_A3()`　`L131`　—　原地跳跃：下蹲→蹬伸→腾空（严格抛物线）→落地缓冲→回升
- `case_A7()`　`L172`　—　下蹲捡物：蹲下→伸手接触地面物体→拿起到手中→站起（物体随手上升）
- `case_A4()`　`L224`　—　转身180：头-躯干-脚顺序自然，无瞬间翻转
- `case_A5()`　`L256`　—　挥手：抬右臂 → 掌摆动，肩肘腕联动，肘不反折、臂不超伸
- `case_A6()`　`L281`　—　踢球：抬腿踢中球 → 球飞出；接触为接触非穿透、动量守恒、支撑脚不浮空
- `case_B8()`　`L331`　—　拿杯子：手伸向杯子→手指闭合(attach)→杯固定在手中→移动时不掉落
- `case_B9()`　`L398`　—　放下杯子：手移到桌面→张开手指(detach)→杯留在桌面→不穿透桌面

### `tests/cases_carry.py`

（缺一句话职责）

- `case_E26()`　`L106`　—　搬运箱子：抱起 → 行走 → 放下，箱体不穿手、不脱手、脚不滑步

### `tests/cases_creature.py`

（缺一句话职责）

- `case_G37()`　`L31`　—　G37 攀岩：三点支撑 / 支撑相零滑移 / 不穿壁 / 帧间平滑。
- `case_G38()`　`L67`　—　G38 鱼游：脊椎段长守恒 / Strouhal 区间 / 帧间平滑。
- `case_G39()`　`L96`　—　G39 四足六步态：支撑足缺口 / 足端滑移 / 帧间平滑。

### `tests/cases_crowd.py`

（缺一句话职责）

- `case_D24()`　`L114`　—　D24 三角色互相碰撞：彼此阻挡/绕开，不重叠，不抖动
- `case_D21()`　`L162`　—　D21 两人击掌：靠近 → 抬臂拍合 → 分开；不穿模、不跳变

### `tests/cases_g36.py`

（缺一句话职责）

- `case_G36()`　`L49`　—　ADDITIVE 三能力接线：gaze_shift / finger_tap / page_flip 叠加到 gait

### `tests/cases_gap.py`

（缺一句话职责）

- `case_B12()`　`L103`　—　B12 推箱子→箱子滑行：penetration_m + momentum_err。
- `case_B13()`　`L120`　—　B13 拉绳子：frame_jump_ratio + penetration_m（绳节不沉地）。
- `case_B14()`　`L140`　—　B14 开门：frame_jump_ratio + penetration_m（门不反向穿框）。
- `case_C15()`　`L158`　—　C15 球撞多米诺：momentum_err + penetration_m。
- `case_D23()`　`L167`　—　D23 猫从腿间穿过：float_m + penetration_m（四足至少一脚着地）。
- `case_E25()`　`L181`　—　E25 圆盘纯滚落：frame_jump_ratio + energy_gain。
- `case_E27()`　`L203`　—　E27 投掷命中移动靶：momentum_err + penetration_m。
- `case_E29()`　`L212`　—　E29 推倒墙/方块散落：penetration_m + energy_gain。
- `case_F30()`　`L239`　—　F30 高速球 CCD：口径为「不隧穿」+ 帧间一致性。
- `case_F31()`　`L253`　—　F31 宽相：penetration_m（判据改动理由见模块口径声明）。
- `case_F32()`　`L263`　—　F32 零重力：momentum_err + penetration_m。
- `case_F33()`　`L273`　—　F33 摩擦：momentum_err（无摩擦工况）+ penetration_m。
- `case_F34()`　`L287`　—　F34 初始重叠自动分离：penetration_m（判据改动见模块口径）。

### `tests/cases_mixed.py`

（缺一句话职责）

- `case_H40()`　`L191`　—　H40 混合场景：7 类实体同时间轴、同世界坐标下的接口一致性。

### `tests/cases_pass.py`

（缺一句话职责）

- `case_D22()`　`L59`　—　两人传球：A 投 -> B 接 -> B 投回 -> A 接

### `tests/cases_phenom.py`

（缺一句话职责）

- `case_P41()`　`L26`　—　P41 树叶飘落：终端速度远低于自由落体 / 水平漂移 / flutter 涌现。
- `case_P42()`　`L39`　—　P42 墙体开裂：静置稳定 / 断键 / 多碎块 / 球减速 / 碎块位移有界。
- `case_P43()`　`L52`　—　P43 水流冲击地面：不穿地 / 横向铺展 / 粒子不丢 / 密度收敛。
- `case_P44()`　`L65`　—　P44 牛顿摆：末球弹出 / 中间球窗口内静止 / 能量守恒。
- `case_P45()`　`L78`　—　P45 转台：离心滑移 / 被甩向外 / 科氏横向偏转 / 低速不滑移。

### `tests/cases_phys.py`

（缺一句话职责）

- `resample_tracks(tracks, sim_dt, fps, duration)`　`L45`　—　把固定步长仿真轨迹重采样为视频帧序列，使物理时间 == 视频时间
- `case_C18()`　`L125`　—　弹球：反弹高度逐次衰减 = 前一次 e^2，不穿地，不增能
- `case_C20()`　`L155`　—　两球对撞：等质量交换速度、异质量动量守恒，不穿模
- `case_C16()`　`L220`　—　堆叠方块：重力下稳定，不塌陷、不抖动、不穿模
- `case_C17()`　`L243`　—　斜坡滚球：沿坡加速下滑，不穿斜面，不增能
- `case_C19()`　`L263`　—　摆锤撞击：水平动量守恒（绳为外力，撞击角决定残差），绳长不变，不穿模

### `tests/cases_throw.py`

（缺一句话职责）

- `case_B10()`　`L67`　—　扔球：动力链顺序加速->出手->弹道->落地反弹
- `case_B11()`　`L115`　—　接球：预测拦截点 -> 最小急动度伸手 -> 接触后球停并随手

### `tests/gen.py`

（缺一句话职责）

- `render_case(name, pose_fn, n, out_prefix, yaw, Zc, lane, t_end=90.0, palette=5.0, hand_lod=0.0, extra=None)`　`L79`　—　pose_fn(t) -> J（归一化身高单位）。逐帧渲染并量剪影。
- `main()`　`L237`

### `tests/gen_doc.py`

（缺一句话职责）

- `sheet(title, head, rows, widths)`　`L49`

### `tests/harness.py`

（缺一句话职责）

- `judge(name, val)`　`L37`　—　返回 (是否通过, 阈值, 比较符, 出处)
- `skate_cm_frame(foot_xy_h, fps, H=24.0)`　`L56`　—　脚滑步。foot_xy_h: [(x, y, h)] 每帧，x/y 水平米，h 离地高（米）。
- `float_m(lowest_joint_h)`　`L73`　—　最低关节离地高度序列 → 最大值（>5cm 判浮空）
- `feet_clip_m(foot_a_xy, foot_b_xy)`　`L79`　—　双脚水平距离最小值（<5cm 判互穿）
- `penetration_m(pairs)`　`L90`　—　穿模深度（2D 简化：胶囊/圆重叠深度，取所有对的最大值）。
- `seg_penetration_m(seg_pairs)`　`L104`　—　线段(骨)-圆(物体) 最短距离 → 穿模深度。
- `frame_jump_ratio(disp_seq)`　`L121`　—　disp_seq: 每帧位移（像素或米）。返回 max/中位；中位为 0 时给 inf。
- `peak_rate_dps(rate_seq)`　`L132`　—　角速度序列(°/s) → 峰值。转身/摆臂等旋转动作的时序平滑度判据。
- `jitter_px(frames)`　`L143`　—　帧图序列（灰度数组）→ 平均帧间绝对差（0~255）
- `restitution(h0, h1)`　`L152`　—　e = sqrt(h1/h0)
- `restitution_err(peaks, e)`　`L159`　—　peaks: 各次反弹最高点 [h0, h1, h2...]，检查 h_n = h0 * e^(2n)
- `momentum_err(before, after)`　`L173`　—　before/after: [(m, (vx,vy))] → 总动量相对误差
- `energy_gain(states)`　`L185`　—　states: [(m, v, h)] 每帧 → 若末态能量大于初态则正（能量凭空增加）
- `knee_reflex(hip, knee=1.0, ankle, facing)`　`L198`　—　膝盖是否反折。facing=+1 表示人物朝 +u。
- `elbow_reflex(shoulder, elbow=1.0, wrist, facing)`　`L217`
- `silhouette_gap_px(mask)`　`L236`　—　剪影在 头顶→脚底 区间内的最长空行段（像素）。
- `silhouette_span_ratio(mask, top_y, bot_y)`　`L249`　—　剪影纵向跨度 / 关节投影的头顶点—脚底点距离。
- `mask_iou(a, b)`　`L259`　—　渲染掩膜 vs 胶囊几何真值掩膜的 IoU。
- `report(checks)`　`L268`　—　checks: [(判据名, 实测值)] → 打印表
- `self_check()`　`L280`　—　判据库自检：构造已知答案，确认公式没写反。
- `contact_float_m(lows, contact_mask)`　`L332`　—　接触相浮空：只在标记为触地的帧上量最低关节离地高度，取最大值。
- `ground_penetration_m(heights)`　`L342`　—　地面半空间穿透深度(m)：h<0 即穿地，取最大。
- `flight_g_err(t_rel, h_m=9.80665, g)`　`L347`　—　抛体段二次拟合: h=a t²+b t+c, 弹道应满足 a=-g/2。返回 |(-2a)-g|/g
- `flight_apex_err(apex_rise_m, flight_time_s=9.80665, g)`　`L359`　—　抛体顶点相对误差：实测升高 vs Δs=g·T_F²/8。

### `tests/run_all.py`

（缺一句话职责）

- `case_F35()`　`L28`　—　超长视频 60s：累积误差漂移（RCS 相位漂移 + 里程累加漂移）
- `case_E28()`　`L73`　—　爬梯（E28）：五效应器交替上行 + 抓握期不滑 + 脚踩实横杆
- `main()`　`L155`

### `tools/baseline.py`

复杂度债务棘轮——基线入版本库，只降不升；新增/恶化即 FAIL，修复自动收紧

- `diff(current, baseline, today)`　`L83`　—　比对当前扫描结果与基线。
- `run(today)`　`L135`　—　返回 {"ok":bool, "counts":{...}, "new":[...], ...}
- `update(today, owner, clear_when)`　`L160`　—　重建基线。只应在人工确认后调用（--update）。
- `self_check()`　`L193`　—　自检 7 项：新增FAIL/恶化FAIL/修复报陈旧/变好收紧/逾期升FAIL/移动非新增/依赖缺失必报错。
- `main()`　`L281`

### `tools/batchgate.py`

（缺一句话职责）

- `run(ids, out, timeout, resume, fresh)`　`L88`　—　执行一批用例，结果写 out。返回统计 dict。
- `self_check()`　`L111`

### `tools/clone.py`

（缺一句话职责）

- `scan(root, min_lines, min_tokens=MIN_LINES)`　`L76`
- `main(argv)`　`L108`

### `tools/complexity.py`

圈复杂度门禁——用 lizard 实测 CCN，替代自造的「函数>50行」行数规则

- `scan(root, ccn_design, ccn_hard)`　`L48`
- `run(root)`　`L91`　—　返回 {"ok":bool, "design":[...], "hard":[...], "counts":{...}}
- `self_check()`　`L126`　—　自检 4 项：CCN 判定准、高复杂度抓得到、低复杂度不误报、_bak 被排除。
- `main()`　`L186`

### `tools/consistency.py`

三表一致性：能力注册表 / EXEC 用例表 / 桥接器互为闭包

- `exec_table()`　`L41`　—　从 run_all.py 抽 EXEC 字典：{用例ID: 函数名}。
- `declared_cases()`　`L57`　—　tests/cases.py 里 CASES 登记的用例 ID 集合（门检真正遍历的那张表）。
- `case_funcs()`　`L75`　—　tests/ 下所有 case_XX 函数名（含 cases_*.py 里定义的）。
- `import_list()`　`L92`　—　tests/ 下所有用例文件导入的模块名集合。
- `called_names()`　`L137`　—　tests/ 下实际被调用的函数名集合（含 obj.method 的方法名）。
- `cap_impl_names()`　`L166`　—　{能力名: 该能力可能被调用到的名字集合}。
- `cap_registered()`　`L231`　—　AST 扫描 @capability 装饰器登记的能力名（不 import，避免导入不全）。
- `bridge_kinds()`　`L260`　—　capbridge 的分类结果 {能力名: POSE/ADDITIVE/PHYS/AUX}。
- `run()`　`L275`　—　返回问题列表。
- `self_check()`　`L329`

### `tools/debtledger.py`

（缺一句话职责）

- `split_debt(problems, today=None)`　`L110`　—　把已知债务与新增问题分开，并做 R19 债务体检。
- `report_debt(problems, today=None)`　`L143`　—　打印债务四桶并返回计数 —— check.py::_report 债务段的唯一出口。
- `self_check()`　`L170`　—　自检: 三条路径必须都成立——未到期豁免/到期升级/陈旧报出。

### `tools/docsync.py`

检测 README / INDEX 里的数字声明是否与脚本实测一致，抓"文档说一套、代码是另一套"

- `run(skip_slow, verbose)`　`L141`
- `self_check()`　`L190`　—　自检：造一个必然失配的文档，验证工具真能报警（不静默跳过）。
- `main()`　`L231`

### `tools/efps.py`

有效帧率：渲染了 N 帧不代表画面动了 N 帧

- `scan(paths)`　`L41`　—　paths: 有序图片路径列表。返回 (n, unique, dup_ratio, runs)。
- `collect(target)`　`L63`
- `self_check()`　`L70`　—　自检：造一段"一半帧静止"的合成序列，验证工具能抓到。

### `tools/faultbench.py`

缺陷注入基准：注入已知代码缺陷，实测工具矩阵能否检出，量化召回率并暴露盲区

- `baseline()`　`L198`　—　干净基线的表现：必须全绿，否则基准本身不可信。
- `run()`　`L206`
- `self_check()`　`L231`　—　自检：基准本身必须可信——干净基线全绿、且能抓到大多数人造缺陷。
- `main(argv)`　`L253`

### `tools/gate.py`

统一自检入口：一键跑全部长期工具，汇总退出码，支持 --json 机器可读输出

- `main(argv)`　`L114`

### `tools/layers.py`

分层契约门禁——包装 import-linter，替代自造的 R1(逆向依赖)/R4(上帝包)

- `run()`　`L36`　—　跑 lint-imports，返回 {"ok":bool,"kept":n,"broken":m,"contracts":[...],"error":str|None}
- `self_check()`　`L74`　—　自检 3 项：配置在、CLI 能跑、解析出契约结果。
- `main()`　`L90`

### `tools/motionqual.py`

补齐业界动作质量指标中我们缺失的那几项（稳定性/抖动/自穿透/接触/步态/游动）

- `seg_seg_dist(p1, q1, p2, q2)`　`L51`　—　两条线段最短距离（3D）。用于 PeneBone 骨级穿透。
- `com_2d(pose, joints, masses)`　`L92`　—　质心（水平 x、竖直 z），质量加权。
- `zmp_series(frames, joints=9.80665, masses, g)`　`L105`　—　ZMP 水平位置序列。
- `zmp_stability(frames, joints=0.02, masses, feet, contact_thresh)`　`L125`　—　动力学稳定性: ZMP 落在支撑多边形（2D 退化为支撑区间）外的帧占比。
- `jitter_accel(frames, joints)`　`L157`　—　关节加速度抖动。
- `pene_bone(frames, bones, radius=0.02, skip_adjacent=True)`　`L189`　—　骨级穿透深度 PeneBone。
- `contact_f1(pred_contact, gt_contact=None, hand_obj_dist)`　`L219`　—　接触质量: 精确率 / 召回率 / F1 / 接触距离。
- `duty_factor(contact_seq)`　`L264`　—　占空比 duty factor: 一个步幅周期内该足触地的时长占比。
- `footfall_phases(contact_seq)`　`L275`　—　提取落脚相位（触地起始时刻 / 周期），用于算相对相位。
- `relative_phase(ref_seq, other_seq)`　`L287`　—　相对相位: other 足相对参考足（如 LH）的触地相位滞后，归一到 [0,1)。
- `wave_ratio(spine, body_len)`　`L301`　—　游动波长 / 体长比。
- `strouhal(freq_hz, amp_m, speed_mps)`　`L325`　—　Strouhal 数 St = f * A / U。
- `self_check()`　`L355`　—　自检: 每条指标都要能"测出已知答案"，否则等于没有牙齿。

### `tools/mutate.py`

判据效力变异测试：给判据注入必错的坏输入，仍判 PASS 即判据无牙齿

- `run_mutants()`　`L85`　—　返回 (killed, survived, skipped)。
- `margin(val, thr, op)`　`L112`　—　阈值裕度。返回相对裕度，越小越危险。
- `self_check()`　`L124`

### `tools/presearch.py`

（缺一句话职责）

- `load_formula()`　`L101`　—　前置库源 1：公式注册表（65 条）。
- `load_caps()`　`L160`　—　前置库源 2：能力表出处（源码静态扫 @capability）与搜索提示。
- `load_docs()`　`L204`　—　前置库源 3：docs/ 下的踩坑记录，按二级标题切块。
- `index_all()`　`L233`　—　汇总三个源，附带导入失败的可见警告。
- `search(query, top=6)`　`L241`　—　本地检索：按覆盖率排序，返回 (命中项, 最高分, 警告)。
- `run(query, top=6)`　`L263`　—　主流程：本地命中达阈值 → INTERNAL；否则 → WEB_NEEDED。
- `panel()`　`L293`　—　面板：前置库现有条目按组统计，缺口一目了然。
- `main()`　`L313`　—　命令行入口：查询 / --panel / --json。

### `tools/provenance.py`

核验判据阈值与其出处自洽、并探测"先调阈值让它过、后补出处"的 HARKing 行为

- `check_selfconsistency(crit)`　`L57`　—　crit: [(name, thr, src)]，默认从 harness.CRIT 读。返回 (issues, compared, uncompared)。
- `check_harking(relpath)`　`L150`　—　返回 (issues, n_commits, note)。
- `run(crit)`　`L171`
- `self_check()`　`L179`
- `main()`　`L201`

### `tools/reach.py`

（缺一句话职责）

- `all_py()`　`L40`
- `rel(p)`　`L47`
- `mod_name(relpath)`　`L51`　—　把文件路径转成可能的模块名：目录用 . 连接，.py 去掉。
- `imports_of(path)`　`L59`　—　收集该文件 import 的目标（相对层级 + 绝对名）。
- `main()`　`L133`

### `tools/refcheck.py`

核验收工判据/文档里引用的 arXiv 与 DOI 是否真实存在、标题是否与判据语义相关，抓"贴牌引用"

- `run(offline)`　`L372`　—　返回 (issues, unchecked, verified, skipped)。
- `self_check()`　`L394`
- `verdict_of(issues, verified, unchecked)`　`L427`　—　统一的通过判定。返回 (rc, 说明)。
- `main()`　`L441`

### `tools/repro.py`

假阳性豁免验证：声称假阳性必须附可执行最小复现，跑得通才算，跑不通按真问题处理

- `verify(item, timeout=120)`　`L60`　—　跑一条豁免的复现脚本。
- `self_check()`　`L94`　—　自检：内置三个探针，正反两面都要对。
- `main()`　`L127`

### `tools/smell.py`

代码异味检查：补 faultbench 实测暴露的 8 类静态盲区（静默异常/判据恒真/自检空转等）

- `check_file(path)`　`L240`　—　对单个文件跑全部 S 规则，返回问题列表。
- `collect(target)`　`L266`　—　扫全项目（或指定目录）的代码异味。
- `self_check()`　`L279`　—　自检：造一个含各类异味的样本，验证规则真能抓到。
- `main(argv)`　`L322`
