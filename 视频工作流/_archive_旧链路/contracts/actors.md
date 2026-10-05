[S] actors @ATOM/rule  d2  in=5  gen:contract_gen
does: actors.py —— 可动者登记 + 动作能力白名单 + 硬报错
api: require, check_shot, check_body_type, wind_response, missing_actor_assets
const: BASE, CHAR_DIR, BG_DIR, ACTORS, CAPABILITY, BG_STATIC, BODY_TYPES
impl: 入口 require
up: physics
down: environment,render_desert_banner,render_gate_banner,render_v4,render_v4_main
edit: environment,physics,render_desert_banner,render_gate_banner,render_v4,render_v4_main   # 改actors须同步核对这些文件
rule: T11 T16
why : IMPROVE_actors.md
