# IMPROVE_solver_check —— 改进措施（改前必读）

1. 断言自身也要证伪：本模块已 4 次"自检假 PASS"
   （framerate 正则/AST 扫描扫不到、transient 断言取绝对量、
    复用注入 reuse=none 仍 PASS、图集规划器建了没接入）
2. 每次新增检查项，必须注入违规看它是否 FAIL。
3. 本文件从 solver.py 切出后，solver.py 用懒加载调用破环（业界允许）。
