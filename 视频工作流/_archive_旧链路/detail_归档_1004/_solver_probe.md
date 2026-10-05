[FACT] _solver_probe   163行   机器生成，勿手改
doc: 探针与容纳性校验：先 8 格验一致性再升级（铁律48）。
api:
  L38 containment_check(cell_bgra,cw,ch,policy,conf)  # 单格容纳性校验（铁律47）。
  L81 probe_plan(ans,probe_max)  # 【铁律48】探针计划：先出 min(probe_max, N) 格验一致性，通过才升级。
  L98 probe_check(sheet_path,cols,rows,n,policy,conf)  # 【铁律48】探针一致性 4 项（对应业界"脸/衣服/配色/比例"）。
internal:
  L17 _cell_policy(spec_or_pol)
  L32 _conf(key)
calls_in: containment_check→_cell_policy, probe_check→_cell_policy, probe_check→containment_check
calls_out: areas,bhs,bws,c,cents,cols_,conts,cv2,cx,cy,det,np,pol,sel,v,xs,ys
guard: raise@L23, return@L59, raise@L107
up: _solver_base
down: _chk_base,_chk_sheet,solver
