[FACT] genqueue   250行   机器生成，勿手改
doc: genqueue · 生图任务队列（铁律81-85）
api:
  L26 plan(objects)  # objects: [{"物体":str,"族":str,"spec":dict}] -> 任务队列
  L62 build_prompt(task)  # 只由该 task 的 spec 组装，禁引入任何其他物体
  L86 next_task(q,done)  # 一次只返回一个未完成任务；done 为已 accept 的 id 集合
  L94 accept(q,tid,report)
  L98 reject(q,tid,reason)
  L110 self_check()
internal:
  L50 _declared_slots(fam)
  L105 _chk(name,ok,info)
calls_in: build_prompt→_declared_slots, self_check→_chk, self_check→build_prompt, self_check→next_task, self_check→plan
calls_out: PS,TPL,done,leak,leak2,o,params,ph,r,re,slots,sv,t,task,tasks
guard: raise@L28, return@L54, raise@L74, return@L80, raise@L99
const: _KIND[5], _ID_KEYS[7]
main: __main__@L249  self_check@L110
up: pose,prompt_tpl
down: build_phase_gen,build_util,build_video,driver
