[S] chroma_selfcheck @ATOM/img  d2  in=1  gen:contract_gen
does: chroma 的自检/检查逻辑（由 _extract_tool.py 从 chroma.py 抽出）
api: self_check
impl: 入口 self_check
up: chroma
down: chroma
edit: chroma   # 改chroma_selfcheck须同步核对这些文件
rule: T15 T18
why : IMPROVE_chroma_selfcheck.md
