# loop_engine ·黄 按需调度+tag依赖闭包+拓扑序+耗时统计
史:notes/loop_engine.md

接口: System(name,init_fn,update_fn,deps).enable/disable,
      LoopEngine.register/bind_tag/set_always/resolve/configure/run/
      order/report/reset_stats, **self_check**

**self_check()（铁律26）**
`python3 loop_engine.py` 默认自检，不渲染。检查项：
  1. 依赖闭包递归展开（启用 physics 自动拉起 skeleton）
  2. 拓扑序：composite/subtitle 必须排最后
  3. 换 ctx 必须重新 init（绑定 ctx id）—— 否则第二镜起空镜
  4. 禁用系统零调用（按需调度真的省了）
  5. 【铁律28】run(fps) 默认取 framerate.FPS，不得写死 60
  6. order 缓存 _order 在 register 后失效（新增系统须重排）

约束: composite/subtitle 必须 set_always，否则 canvas 为 None
约束: init 状态绑定 ctx 身份(id)，换 ctx 必须重新 init
