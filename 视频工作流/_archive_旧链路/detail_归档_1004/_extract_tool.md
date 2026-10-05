[FACT] _extract_tool   134行   机器生成，勿手改
doc: 通用函数抽取工具：把源模块中指定函数搬到新模块，原模块留 wrapper 重导出。
api:
  L16 collect_top_defs(src)  # 顶层定义的函数/类/变量符号集合
  L32 collect_refs(func_src,top_names)  # 函数体内引用了哪些顶层符号（含嵌套函数内）
  L45 get_import_block(src)  # 抽取源文件的顶层 import 区源码（到第一个非 import 语句为止）
  L61 extract(src_module,new_module,func_names,dry)
calls_in: extract→collect_refs, extract→collect_top_defs, extract→get_import_block
calls_out: ast,names,new_module,os,out,refs,spans,src,src_module
guard: raise@L83, return@L121
main: __main__@L131
up: -
down: -
