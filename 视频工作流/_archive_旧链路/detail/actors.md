[FACT] actors   199行   机器生成，勿手改
doc: actors.py —— 可动者登记 + 动作能力白名单 + 硬报错
api:
  L106 require(action,actor)  # 单个 (actor, action) 能否被供给。返回 None 或错误串。
  L124 check_shot(name,decl)  # decl: [(actor, action), ...]
  L143 check_body_type()  # 每个 actor 必须声明合法 body_type
  L156 wind_response(name,v)  # 该 actor 在风速 v 下的响应（面积/受力/加速度/风级）
  L170 missing_actor_assets()  # actor 资产缺口（可动件 file=None 视为待生成）
calls_in: check_shot→require
calls_out: ACTORS,CAPABILITY,a,errs,os,out,pr,v
guard: return@L109, return@L112, return@L114, return@L117, return@L160
const: BASE, CHAR_DIR, BG_DIR, ACTORS[10], CAPABILITY[10], BG_STATIC[8], BODY_TYPES[3]
main: __main__@L182
up: physics
down: environment,render_desert_banner,render_gate_banner,render_v4,render_v4_main
