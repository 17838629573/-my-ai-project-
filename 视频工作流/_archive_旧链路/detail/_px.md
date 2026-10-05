[FACT] _px   178行   机器生成，勿手改
doc: _px.py —— 像素/米 换算的**唯一**口径
api:
  L37 px_per_m(ref_px,ref_m,*,crop_top)  # 像素每米。唯一合法入口。
  L53 canvas_px_per_m(canvas_h,crop_top)  # 返回 (用画布总高的口径, 用可见高的口径) 及其比值。
  L90 to_px(real_m,ppm)  # 米 → 像素（四舍五入取整）。
  L95 to_m(px,ppm)  # 像素 → 米。
  L102 world_y_from_canvas(y_canvas,*,crop_top)  # 画布 y → 世界坐标 y（米），以墙顶/地平线为 y=0，向下为正。
  L110 canvas_y_from_world(y_world,*,crop_top)  # 世界坐标 y（米）→ 画布 y 像素。逆变换。
  L125 self_check()  # _px 自检：口径唯一、往返一致、边界拦截。
calls_in: self_check→canvas_px_per_m, self_check→canvas_y_from_world, self_check→px_per_m, self_check→to_m, self_check→to_px, self_check→world_y_from_canvas
calls_out: ck
guard: raise@L46, raise@L48, raise@L97
const: CANVAS_W=1080, CANVAS_H=1080, CROP_TOP_DEFAULT=196, VISIBLE_H_DEFAULT
main: __main__@L176  self_check@L125
up: -
down: build_phase_asset,build_phase_setup,physics
