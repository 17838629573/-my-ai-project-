[S] zmp @ATOM/phys  d0  in=0  gen:contract_gen
does: X_c 失衡判定：ZMP + 支撑多边形。
api: support_polygon, com_projection, zmp_dynamic, self_check
impl: self_check → com_projection → zmp_dynamic；内部helper 3个
why : IMPROVE_zmp.md
