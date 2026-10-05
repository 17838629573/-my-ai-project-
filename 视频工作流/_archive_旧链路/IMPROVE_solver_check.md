# IMPROVE_solver_check —— 改进措施（改前必读）

1. 断言自身也要证伪：本模块已 4 次"自检假 PASS"
   （framerate 正则/AST 扫描扫不到、transient 断言取绝对量、
    复用注入 reuse=none 仍 PASS、图集规划器建了没接入）
2. 每次新增检查项，必须注入违规看它是否 FAIL。
3. 本文件从 solver.py 切出后，solver.py 用懒加载调用破环（业界允许）。

---

---

---
## Y-Statement（gen:why_apply 勿手改）

meta: solver_check
处境: 1. 断言自身也要证伪：本模块已 4 次"自检假 PASS"
问题: 1. 断言自身也要证伪：本模块已 4 次"自检假 PASS"
决定: 2. 每次新增检查项，必须注入违规看它是否 FAIL。
否决方案: N/A 无记录（原文未记否决方案）
收益: N/A 无记录（原文未记收益）
代价: 1. 断言自身也要证伪：本模块已 4 次"自检假 PASS"
依据出处: N/A 无记录（本文件为踩坑记录，依据见 solver_survey）
