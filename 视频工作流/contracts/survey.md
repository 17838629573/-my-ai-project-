# survey（问卷段）—— 契约（明文）

文件：solver_survey.py（246 行）
依赖：无（零依赖，最先被加载）
被依赖：solver、solver_check

改前必读：
  IMPROVE_solver_survey.md   ← 真坑与待办，改这块前先读

边界（铁律36/37）：
  提问区禁止出现具体物体名；示例区必须硬编码（心智模型）
  两者用 BEGIN/END EXAMPLES 隔开，自检剔除示例区后扫描
