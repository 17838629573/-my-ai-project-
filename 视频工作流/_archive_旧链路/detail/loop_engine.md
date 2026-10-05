[FACT] loop_engine   328行   机器生成，勿手改
doc: 按需调度引擎 —— 解决"全量跑"问题
api:
  L219 self_check()  # 只读自检 + 最小调度冒烟，不渲染。返回 (ok, 项数)
calls_out: eng,eng2,eng3,eng4,log
main: __main__@L325  self_check@L219
up: framerate
down: render_v4
