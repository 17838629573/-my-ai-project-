[FACT] build_phase_time   39行   机器生成，勿手改
doc: 出片前置：周期与步态时间参数。
api:
  L11 flag_period_s(spec)  # 旗帜周期：优先 solver 输出；缺失由数值层按族+特征长度+风速算出。
  L29 gait_time(spec)  # 步态：speed = stride / cycle（业界公式），cadence=120/cycle 步/分。
  L37 durations(period_flag,cycle,n_flag,n_man)  # 逐帧时长：均匀切分周期。帧数由采样率决定，禁硬编码帧数。
calls_out: _o,spec
up: wind_response
down: build_video
