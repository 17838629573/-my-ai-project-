[FACT] skeleton_runtime   244行   机器生成，勿手改
doc: Spine 格式骨架求解器 —— 不需要官方 runtime
api:
  L37 mat_mul(A,B)  # 2x3 仿射矩阵相乘 A @ B
  L49 mat_local(x,y,rot_deg,sx,sy)  # 骨/附件的局部变换：平移 -> 旋转 -> 缩放
  L61 mat_apply(M,px,py)
  L66 mat_inverse(M)
  L206 apply_animation(sk,anim,time)  # 把动画某时刻的 rotate/translate 写入 sk.pose。
internal:
  L219 _interp(keys,time,default,idx)
calls_in: apply_animation→_interp
calls_out: anim,arr,k,math,np,sk,tl
guard: return@L70, return@L220, return@L227, return@L229
main: __main__@L242
up: skeleton_runtime_selfcheck
down: skeleton_runtime_selfcheck,systems,systems_phys,systems_selfcheck,systems_view
