[FACT] deps_sync   99行   机器生成，勿手改
doc: deps_sync.py — 从源码 import 自动反推 deps.md 依赖侧（铁律：禁止手填依赖）
api:
  L16 scan(path)
  L30 local_modules(root)
  L34 build(root)
  L47 has_selfcheck(m)
  L54 topo(deps)  # 按依赖深度拓扑分层：无依赖 L0，依赖 L0 的 L1 ...
  L67 render(deps)
calls_in: build→local_modules, build→scan, render→has_selfcheck, render→topo
calls_out: a,ast,bucket,depth,f,lines,n,os,out
const: EXTERNAL, BREAK, CORE
main: __main__@L92
up: -
down: -
