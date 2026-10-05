[FACT] scale_map   244行   机器生成，勿手改
doc: scale_map.py — 比例尺层：把「米」换算成「像素」
api:
  L31 build_scale_map(scene)  # 米 → 像素。所有部件对同一个命名参照物取尺度。
  L96 verify(smap,measured)  # AI 量出资产实际像素高 → 代码比对 target_px。超阈值即 FAIL（铁律64）。
  L130 prompt_block(smap)  # 生图用米制描述块（铁律65）。AI 无内在尺度感，必须显式注入。
  L150 self_check()
internal:
  L24 _need(d,keys,where)
calls_in: build_scale_map→_need, self_check→build_scale_map, self_check→prompt_block, self_check→verify
calls_out: derived,fails,lines,m,o,objs,report,scene,tol
guard: raise@L26, raise@L39
const: REQUIRED_CANVAS[2], REQUIRED_REF[3], PIVOTS[3], DEFAULT_TOL[1]
main: __main__@L243  self_check@L150
up: -
down: build_phase_setup,build_util,build_video,shot_plan
