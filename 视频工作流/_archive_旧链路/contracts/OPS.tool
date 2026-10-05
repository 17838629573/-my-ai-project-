[M] OPS/tool  S=7: _extract_tool,_extract2,_migrate_common,deps_sync,_split_sheet,_split_tool,_split_plan
api: _extract_tool.collect_top_defs(src) | _extract_tool.collect_refs(func_src,top_names) | _extract_tool.get_import_block(src) | _extract_tool.extract(src_module,new_module,func_names,dry) | _extract2.extract(src_path,names,new_path,new_header,wrapper) | _migrate_common.active(path) | _migrate_common.main() | deps_sync.scan(path) | deps_sync.local_modules(root) | deps_sync.build(root) …
rule: T44
uses: ATOM/img
inner=0  selftest=7/7
