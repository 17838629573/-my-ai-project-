[S] _split_tool @OPS/tool  d0  in=0  gen:contract_gen
does: 通用切分工具：把 solver.py 的一个行区间搬到新模块，并在 solver.py 留 facade。
api: find_line, top_names, used_names, defined_names, main
impl: main → _insert_facade → defined_names → find_line；内部helper 1个
why : IMPROVE__split_tool.md
