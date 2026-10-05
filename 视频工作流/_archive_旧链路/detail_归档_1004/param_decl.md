[FACT] param_decl   242行   机器生成，勿手改
doc: param_decl — 参数声明与反问接口
api:
  L78 verify(pname,p)  # 校验 AI 提供的参数：值 / 单位 / 来源 / 区间 四件套。缺一即拒。
  L102 require(pname,family,why,unit_hint,hint)  # 读取参数。不存在 → 抛 AskAI（反问，不兜底）。
  L113 have(pname)  # 参数是否已声明（不抛异常）。
  L118 save(pname,value,unit,source,rng,family)  # 把 AI 作答落盘。写入前先验一次，脏数据不入库。
  L130 audit()  # 审计：列出所有已声明参数的来源与区间。无来源的会被 verify 拦。
  L143 self_check()  # 自检 8 项，含 2 项证伪。
internal:
  L68 _load()
calls_in: require→_load, require→verify, have→_load, save→_load, save→verify, audit→_load, audit→verify, self_check→_load, self_check→require, self_check→save, self_check→verify
calls_out: _ast,_bad,bad,e,f,json,ok,os,report,store
guard: return@L69, raise@L80, raise@L86, raise@L88, raise@L91, raise@L94, raise@L96, raise@L108
const: _HERE, PARAMS_FILE
main: __main__@L237  self_check@L143
up: -
down: _surface,cloth_aero,cloth_wire
