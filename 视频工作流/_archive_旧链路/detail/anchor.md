[FACT] anchor   284行   机器生成，勿手改
doc: anchor.py —— 物理点锚点层
api:
  L44 dimensionless(L,sigma,B,U,H)  # R1 = 质量比 M*      = sigma/(rho_f·L)
  L57 judge_regime(R2,family)  # Izawa 2024 实测区间 —— 仅对 cantilever 有效。
  L71 strouhal_freq(U,L,a_over_l)  # St = 2A·f/U  →  f = St·U/(2A)
  L97 cantilever_points(n,waves)  # 悬臂梁物理点：s=0 clamped（位移0、切角0），s=1 自由端（弯矩0）
  L114 pendulum2_points(n,waves)  # 二级摆：顶端受迫振动（跟随驱动点，振幅已最大）+ 自身摆动
  L130 build_anchor(name,L,H,sigma,B,U,family,n,a_over_l)  # 返回完整锚点包：无量纲数 + regime + 周期 + 物理点表 + 硬约束
  L190 self_check()
internal:
  L89 _phi(s)
  L163 _constraints(family,regime,L,T,a_pp)
calls_in: cantilever_points→_phi, build_anchor→_constraints, build_anchor→cantilever_points, build_anchor→dimensionless, build_anchor→judge_regime, build_anchor→pendulum2_points, build_anchor→strouhal_freq, self_check→build_anchor, self_check→cantilever_points, self_check→dimensionless, self_check→judge_regime, self_check→pendulum2_points, self_check→strouhal_freq
calls_out: ast,c,dm,fr,inspect,math,pts
guard: return@L62, return@L64, return@L66, raise@L79, raise@L138, raise@L140
const: RHO_F=1.225, NU=1.5e-05, G=9.81, ST_TARGET=0.2, BETA1=1.8751, R2_STRAIGHT=0.00406, R2_DEFLECT=0.00172, FAMILIES[4]
main: __main__@L283  self_check@L190
up: framerate
down: _chk_base,_solver_chain,_solver_geom
