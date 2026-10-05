[S] _extract_tool @OPS/tool  d0  in=0  gen:contract_gen
does: 通用函数抽取工具：把源模块中指定函数搬到新模块，原模块留 wrapper 重导出。
api: collect_top_defs, collect_refs, get_import_block, extract
impl: 入口 collect_top_defs
why : IMPROVE__extract_tool.md
