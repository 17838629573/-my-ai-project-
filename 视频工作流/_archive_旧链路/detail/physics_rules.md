[FACT] physics_rules   163行   机器生成，勿手改
doc: physics_rules.py —— 物性推导与风力计算
api:
  L64 volume_of(mass,rho)  # V = M / ρ
  L69 frontal_area(mass,kind,rho,trunk)  # A = k · V^(2/3)
  L82 vogel_exponent(kind,flexible)  # 柔物体返回 Vogel 指数 B（负），刚体返回 0.0
  L89 drag_force(v,area,cd,rho,b)  # F = ½·ρ·v²·Cd·A         刚体
  L101 accel(force,mass)  # a = F / m
  L108 beaufort(v)  # 风速 → (等级, 描述)
  L119 raindrop_v(d_mm)  # 雨滴终端速度 Gunn-Kinzer 拟合，R²=0.999
  L124 describe(name,mass,kind,wind_v,cd,flexible)  # 一行诊断：物性 → 受力 → 加速度
calls_in: frontal_area→volume_of, describe→accel, describe→beaufort, describe→drag_force, describe→frontal_area, describe→vogel_exponent
calls_out: B_VOGEL,K_SHAPE,_common,math
guard: return@L75, return@L84, return@L94, return@L103
const: RHO_AIR=1.225, G=9.81, RHO_TISSUE=1000.0, K_SHAPE[8], TRUNK_EXPONENT=1.0, B_VOGEL[4], BEAUFORT[11]
main: __main__@L135
up: _common
down: environment,systems,systems_phys,systems_selfcheck,systems_view
