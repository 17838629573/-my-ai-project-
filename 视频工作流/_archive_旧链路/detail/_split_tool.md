[FACT] _split_tool   147行   机器生成，勿手改
doc: 通用切分工具：把 solver.py 的一个行区间搬到新模块，并在 solver.py 留 facade。
api:
  L21 find_line(lines,marker,which)
  L28 top_names(tree)  # 文件顶层定义/赋值/导入的名字 -> 需要的来源
  L46 used_names(block_src)
  L61 defined_names(block_src)
  L76 main()
internal:
  L129 _insert_facade(rest,newmod,need_sorted,facade)
calls_in: main→_insert_facade, main→defined_names, main→find_line, main→top_names, main→used_names
calls_out: _re,a,ast,b,block,imp_lines,l,line,lines,out,s_head,txt,used
guard: raise@L23, raise@L81
main: __main__@L146
up: -
down: -
