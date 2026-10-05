[FACT] prompt_tpl   324行   机器生成，勿手改
doc: prompt_tpl —— 按族抽象的生图提示词模板（铁律81-85）
api:
  L141 scale_slots(family)  # 族的主尺度槽名。未知族报错（禁静默降级，铁律31）。
  L149 families()
  L160 build(family,params)  # 按族渲染提示词。未知族报错（铁律84），缺槽报错（铁律31）。
  L189 structural_pose(family,solved)  # 把代码算出的量转成结构性姿态文本（铁律83：禁模糊词）。
  L254 self_check()
internal:
  L153 _require(family,params)
  L222 _chk(name,ok,info)
  L227 _scan(text)
  L232 _scan_targets()
calls_in: build→_require, build→families, self_check→_chk, self_check→_scan, self_check→_scan_targets, self_check→build, self_check→families, self_check→structural_pose
calls_out: ast,lines,ok,p,parts,solved
guard: raise@L143, raise@L156, raise@L162, raise@L191, raise@L193, raise@L195, return@L207, return@L212
const: EXAMPLES[5], TPL[5], DISCIPLINE='【生图纪律·代码强制】\n1. 一次只生成【一个物体】的【一类图】，禁把多个物体的描述混在同一批。\n2. 本批未通过验收前，禁止开始下一批。\n3. 骨架图/控制图【永不进画面】——它只是计算中间量。', HARDCODE_BAN[10], SCALE_SLOT[5]
main: __main__@L322  self_check@L254
up: -
down: build_phase_gen,genqueue
