[FACT] chroma_selfcheck   128行   机器生成，勿手改
doc: chroma 的自检/检查逻辑（由 _extract_tool.py 从 chroma.py 抽出）
api:
  L10 self_check()  # 用【合成图】自检，不依赖资产目录。返回 (ok, 项数)
calls_out: alpha,dst,m,np
up: chroma
down: chroma
