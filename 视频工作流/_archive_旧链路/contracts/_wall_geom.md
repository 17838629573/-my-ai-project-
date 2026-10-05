[S] _wall_geom @ATOM/cam  d1  in=1  gen:contract_gen
does: wall geometry —— 墙体落点的透视几何（从 _surface.py 拆出）。
api: wall_top_y, wall_depth_for_top
impl: 入口 wall_top_y
up: _perspective
down: _surface
edit: _perspective,_surface   # 改_wall_geom须同步核对这些文件
why : IMPROVE__wall_geom.md
