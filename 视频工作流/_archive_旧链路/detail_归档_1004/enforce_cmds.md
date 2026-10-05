[FACT] enforce_cmds   298行   机器生成，勿手改
doc: enforce 的自检/检查逻辑（由 _extract_tool.py 从 enforce.py 抽出）
api:
  L12 cmd_status()  # 红黄绿 = 机器判定，禁止手填（此前手填导致与事实不符）
  L51 cmd_validate()
  L154 cmd_check_contract(name)
  L162 cmd_check_deps()
  L182 cmd_check_evidence(code,evidence)
  L191 cmd_gate(kind,stage)
  L203 cmd_check_assets()  # 资产硬阻断：主角/配角/道具/走路帧 缺一即 FAIL。
calls_out: _os,bg_ok,cs,cv2,deps,errs,f,fn,json,layer,os,p,py_compile,r,rep,spec,subprocess,time,warns
guard: return@L143, return@L156, return@L174, return@L185, return@L192, return@L288
up: character_sheet,chroma,enforce
down: enforce
