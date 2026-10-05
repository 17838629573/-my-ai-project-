[FACT] driver   361行   机器生成，勿手改
doc: driver —— 先判族，再选驱动器（铁律77-80）
api:
  L115 classify(obj)  # 校验物体的族声明。族由 AI 判（铁律79），代码只校验。
  L130 plan(objects)  # 分派驱动器，并输出 AI 必做清单（铁律80：不许静默降级）。
  L182 briefing(objects,tool_caps)  # 代码 -> AI 的任务包。程序做不到的逐条提醒。
  L273 self_check()
internal:
  L212 _genqueue_brief(objects)
  L239 _chk(name,ok,info)
  L244 _scan_targets()
  L267 _scan_hardcode(src)
calls_in: plan→classify, briefing→_genqueue_brief, briefing→plan, _scan_hardcode→_scan_targets, self_check→_chk, self_check→_scan_hardcode, self_check→_scan_targets, self_check→briefing, self_check→plan
calls_out: GQ,ast,lines,o,obj,ok,out,parts
guard: raise@L117, raise@L121, raise@L123, raise@L125
const: FAMILIES[7], EXAMPLES[7], HARDCODE_BAN[6]
main: __main__@L359  self_check@L273
up: genqueue
down: solver_survey
