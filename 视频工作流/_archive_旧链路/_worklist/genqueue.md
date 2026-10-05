# FILL genqueue   缺 3 槽位   （模型只填 pick，勿写散文）

## 处境 (context)
已填: 无
  [IMPROVE:IMPROVE_genqueue.md:L51] ## 三、待办（程序做不到，须 AI 或后续模块补）
  [IMPROVE:IMPROVE_genqueue.md:L55] 2. quadruped / rigid 两族只登记了族，**驱动器未实现**：
  [IMPROVE:IMPROVE_genqueue.md:L67] | 250 | genqueue.py | 本轮**新建独立模块**，未塞进 driver |
  [genqueue.py:L22] identity 词：用于检测跨物体污染
  [genqueue.py:L205] 10 证伪：假实现(一次返回全部)必须被 3 检出
  pick: NEW: 生图队列：按物体逐个生成身份参考与序列帧的排队模块（IMPROVE_genqueue.md:67 新建独立模块）

## 决定 (decided)
已填: 无
  [IMPROVE:IMPROVE_genqueue.md:L12] | 身份参考图必须逐物体独立，不对着上一个资产做 | 业界 sprite 管线 |
  [IMPROVE:IMPROVE_genqueue.md:L14] | 模板必须按作用域隔离 | outlierkit |
  [IMPROVE:IMPROVE_genqueue.md:L20] ### 坑1 自检用的 solved 是我手填的 → 违反铁律68
  [IMPROVE:IMPROVE_genqueue.md:L21] 第一次自检第6项 FAIL：`structural_pose` 要求姿态必须来自代码计算。
  [IMPROVE:IMPROVE_genqueue.md:L34] `except ValueError` 的调用方**，改成别的基类会让自检8/9静默失效。
  pick: IMPROVE_genqueue.md:12

## 代价 (accepting)
已填: 无
  [IMPROVE:IMPROVE_genqueue.md:L32] 第71行 raise 它，但类没定义 → 触发时 NameError 而非清晰报错。
  [IMPROVE:IMPROVE_genqueue.md:L46] ### 坑6 证伪14 写法错误
  pick: IMPROVE_genqueue.md:55
