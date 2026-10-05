[FACT] solver_survey   313行   机器生成，勿手改
doc: solver_survey —— 从 solver.py 切出（业界：文件 150-500 行最优）。
api:
  L107 survey()  # 第①步：代码向 AI 提问——本片有哪些物体？（代码不知道，AI 盘）
  L117 inventory(actors)  # 第②步：AI 给物体清单 -> 代码为每个物体反问『哪些相对动、哪些相对静』
  L147 scale_question(objects)  # 第②·五步：比例尺问卷（铁律63）
  L191 assemble(ans)  # 第③步：AI 填完问卷 -> 代码组装成 solver spec + 缺槽清单（AI 去搜）
  L261 briefing_text(b,with_examples)  # 可读任务包。代码输出后 AI 照做即可，不靠记忆（铁律33）。
internal:
  L183 _qname(q)
calls_in: assemble→_qname, assemble→scale_question
calls_out: L,PART_ROLES,_drv,a,ans,b,missing,p,q,qs,ref,slots,specs,v
guard: raise@L119, raise@L187, raise@L193
const: KINDS[6], PART_ROLES[3], DRIVE_SOURCES[4], SLOT_TEMPLATE[4], EXAMPLES[4], HOWTO[6]
up: driver
down: _chk_assemble,_chk_base,_chk_survey,solver
