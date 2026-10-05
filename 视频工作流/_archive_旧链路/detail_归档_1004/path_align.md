[FACT] path_align   127行   机器生成，勿手改
doc: 路径—路面对齐（契约 contracts/path_align.md，铁律95-98）
api:
  L9 normalize_pts(pts,W,H)  # 铁律96：控制点必须在画布内，越界即报错（禁静默裁剪）。
  L26 walkable_band(bg_bgr,y0,y1)  # 铁律95：检测可行走表面。
  L41 is_ground_patch(bg_bgr,x,y,r,depth)  # 判定 (x,y) 周围是否为地面 patch。
  L65 validate_path(pts,bg_bgr,table,n,total)  # 铁律98：沿路径采样，校验是否落在可行走面上。
  L86 visible_path_prompt(pts,half_width_px,px_per_m,material)  # 铁律97：生成"画面内可见"的路面几何描述（禁画布外坐标）。
  L97 self_check()
internal:
  L19 _row_continuity(row)
calls_in: walkable_band→_row_continuity, validate_path→is_ground_patch, self_check→normalize_pts, self_check→validate_path
calls_out: PA,below,bg_bgr,fails,np,patch,rng,row,scores
guard: raise@L12, return@L50, return@L54, return@L114, return@L120
main: __main__@L125  self_check@L97
up: path
down: build_phase_setup
