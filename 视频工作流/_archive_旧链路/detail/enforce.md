[FACT] enforce   205行   机器生成，勿手改
doc: 执行门禁（契约强制性检查）
api:
  L31 parse_deps()  # 解析 deps.md -> (deps, layer, order, runtime)
  L78 module_exists(name)  # 模块名 -> 实际路径（.py 文件或目录），不存在返回 None
  L89 find_cycle(deps)  # DFS 三色标记找环
  L115 local_imports(py_path)  # 扫出文件里 import 的【本地】模块（同目录存在 .py 的）
  L141 cmd_status(*a,**k)
  L146 cmd_validate(*a,**k)
  L151 cmd_check_contract(*a,**k)
  L156 cmd_check_deps(*a,**k)
  L161 cmd_check_evidence(*a,**k)
  L166 cmd_gate(*a,**k)
  L171 cmd_check_assets(*a,**k)
  L176 main()
calls_in: main→cmd_check_assets, main→cmd_check_contract, main→cmd_check_deps, main→cmd_check_evidence, main→cmd_gate, main→cmd_status, main→cmd_validate
calls_out: cleaned,cycles,d,deps,ds,head,ln,m,n,names,order,os,out,path,re,runtime,t
guard: return@L81, return@L83, return@L177, return@L181, return@L183, return@L185, return@L187, return@L189
const: BASE, DEPS, WORKLOG, ACTIVE_SECTIONS[5], DORMANT_SECTIONS[2], MODULES[12]
main: __main__@L201
up: enforce_cmds
down: enforce_cmds,run_batch
