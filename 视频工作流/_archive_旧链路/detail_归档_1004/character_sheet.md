[FACT] character_sheet   324行   机器生成，勿手改
doc: 角色图集 + 映射层
api:
  L121 missing_assets()  # 【已修】status 改为由【文件是否真实存在】推导，不再手填。
  L137 load_native(path,H,W)  # 原生模式：抠像但【不裁剪】，整帧缩放到画布。
  L152 load_scaled(path,target_h)  # 缩放模式：抠像 → 清掩膜 → 裁包围盒 → 按高度缩放。
  L171 resolve(shot_type,pose,frame)  # 由【景别 + 姿态】查图集，返回资产条目。
  L191 measure_native_composition(path,H,W)  # 测量原生资产的构图：头顶留白、底部切点。
  L280 check_naming(directory)  # 返回违例列表，空=通过。新增序列帧后必跑。
  L309 tier_target_h(body_frac)  # 按屏幕占比返回该资产的目标高度。占屏越小越省。
  L317 loop_closed(frames)  # 循环动画首帧必须等于末帧（death 除外）。
calls_in: measure_native_composition→load_native
calls_out: SHEET,bad,cv2,np,os,out,part,stem,tbl,v,xs,ys
guard: raise@L144, raise@L155, raise@L161, raise@L178, return@L199, return@L320
const: BASE, CHAR_DIR, SHEET[8], SUPPORTING[4], EXPRESSION[6], PROP[5], WALK_8FRAME[4], TIER_BY_SHARE[4]
main: __main__@L206
up: chroma,photo_rules
down: _actor_audit,enforce_cmds,film_assemble,film_assemble_render,render_desert_banner,render_gate_banner,render_v4_main
