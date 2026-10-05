[S] _ground_arc @ATOM/path  d0  in=2  gen:contract_gen
does: 地面坐标反投影 + 世界弧长参数化。
api: cam_of, back_project, forward_project, px_per_m_lateral, px_per_m_depth, world_arc_table, at_world_distance, px_arc_to_meter, hw_px_at, self_check
impl: self_check → at_world_distance → back_project → forward_project；内部helper 1个
down: build_phase_render,build_video
edit: build_phase_render,build_video   # 改_ground_arc须同步核对这些文件
rule: T96 T98
why : IMPROVE__ground_arc.md
