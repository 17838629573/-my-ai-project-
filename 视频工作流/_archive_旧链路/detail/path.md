[FACT] path   226行   机器生成，勿手改
doc: 路径约束：把位置表示为「弧长 s + 横向偏移 offset」，使其永远在路径上。
api:
  L13 catmull_rom(p0,p1,p2,p3,u)  # 标准 Catmull-Rom，u∈[0,1]，曲线经过 p1→p2。
  L47 sample(pts,u)
  L51 arc_table(pts,n)  # 累积弧长表：把 u 与弧长 s 对应起来（铁律77 的基础）。
  L80 at_distance(pts,s,table)  # 按弧长取点（等速）。返回 {xy, tangent, u, s}。
  L94 project(pts,x,y,table)  # 世界点 → (弧长 s, 带符号横向偏移 offset)。
  L114 clamp_offset(offset,half_width)
  L120 advance(s,ds,total)
  L124 lookahead(pts,s,da,table)
  L129 self_check()
internal:
  L9 _pt(p)
  L28 _seg(pts,u)
  L63 _u_of_s(table,s)
calls_in: catmull_rom→_pt, _seg→_pt, _seg→catmull_rom, sample→_seg, arc_table→_seg, at_distance→_seg, at_distance→_u_of_s, at_distance→arc_table, project→_seg, project→arc_table, project→at_distance, lookahead→advance, lookahead→arc_table, lookahead→at_distance, self_check→advance, self_check→arc_table, self_check→at_distance, self_check→clamp_offset, self_check→lookahead, self_check→project, self_check→sample
calls_out: fails,math,ss,ugaps
guard: raise@L31
main: __main__@L224  self_check@L129
up: -
down: build_phase_render,build_phase_setup,build_util,build_video,path_align,shot_plan
