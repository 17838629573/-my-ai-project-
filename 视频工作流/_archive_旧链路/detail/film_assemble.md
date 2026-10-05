[FACT] film_assemble   148行   机器生成，勿手改
doc: 镜头装配层 —— 模型填 3 个字段，代码完成全部映射
api:
  L39 sub_shift(img,dx,dy)
  L44 scroll_bg(bg,dx,W,H)
  L49 prep_native(key,W,H)  # 细节资产：整帧缩放到画布，保留生成时的取景
  L56 prep_scaled(key,char_h)  # 全身资产：裁包围盒 -> 按景别人物高度缩放 -> 返回 BGRA 与宽高
  L71 nose_offset_x(st,W,char_w,look)  # 返回人物左上角 x。look=视线/运动方向（left/right）。
  L83 resolve_shot(st,H,W,look)  # 由景别反算：人物像素高 + 脚底 y + 构图 x（脚可能出画）
  L92 plan_resolve(shots,W,H)  # 把 3 字段声明 -> 完整装配参数
  L117 overlay_full(dst,bgra,scale)  # 细节资产整帧贴合（含相机缩放）
  L133 self_check(*a,**k)
  L137 render_one(*a,**k)
internal:
  L106 _pick_asset(shot_type,state)
calls_in: resolve_shot→nose_offset_x, plan_resolve→_pick_asset, plan_resolve→resolve_shot
calls_out: META,NOSEROOM,SHEET,cv2,m,np,os,out,s,v,xs,ys
guard: raise@L62, return@L77, return@L79
const: BASE, BG_DIR, NOSEROOM[8], META[9]
main: __main__@L144  self_check@L133
up: character_sheet,chroma,film_assemble_render,photo_rules,subtitle
down: film_assemble_render,render_v4,render_v4_main
