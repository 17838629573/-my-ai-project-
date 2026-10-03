# solver_check —— 契约（明文）

文件：solver_check.py（612 行）
依赖：solver（懒加载，破环）、solver_survey
被依赖：solver.__main__（懒加载调用）

改前必读：
  IMPROVE_solver_check.md    ← 自检自身的假 PASS 史，改这块前先读

铁律26：无自检=不通过，零输出不算 PASS
铁律：断言本身也要验（本模块已 4 次栽在"自检假 PASS"）
