[FACT] chroma   290行   机器生成，勿手改
doc: 角色层素材处理：色度键抠像 + 去溢色 + 边缘处理
api:
  L28 chroma_key(bgr,ref,softness,shrink,despill)  # 色度键 -> (BGRA 图像, alpha 浮点图)
  L81 trim_alpha(bgra,pad)  # 裁掉全透明外框 + 外扩 pad 像素。
  L97 clean_mask(bgra,thresh,feather)  # 【实测 bug】高斯羽化后角落 alpha 仍有 70/38/58/16，导致
  L122 all_components(mask,thresh,min_area)  # 全量连通域（8 向），按面积降序。铁律44：图集切分要"网格定序 +
  L153 load_character(path,target_h,method,**kw)  # 读角色图 -> 抠像 -> 清掩膜 -> 裁剪 -> 可选缩放。返回 BGRA
  L173 overlay(dst,bgra,x,y,scale)  # 把 BGRA 角色贴到 BGR 画布上（uint16 整数混合，实测比全画布 float 快 4.7x）。
  L204 contact_shadow(w,h,cx,strength)  # 接触阴影：人物脚下没有阴影会'浮空'。返回浮点 alpha 图
  L214 flood_key(bgr,tol,despill,feather)  # 边缘泛洪抠像（Photoshop 魔棒的思路）。
  L282 self_check(*a,**k)
calls_in: load_character→chroma_key, load_character→clean_mask, load_character→flood_key, load_character→trim_alpha
calls_out: a8,bgr,bgra,bw,cv2,f,fg,img,mask,np,out,seeds,xs,ys
guard: return@L90, raise@L158, return@L190
main: __main__@L287  self_check@L282
up: chroma_selfcheck
down: _split_sheet,build_phase_asset,build_util,build_video,character_sheet,chroma_selfcheck,enforce_cmds,film_assemble,film_assemble_render
