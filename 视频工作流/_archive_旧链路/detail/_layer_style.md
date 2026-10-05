[FACT] _layer_style   58行   机器生成，勿手改
doc: 分层合成四要素（铁律101）：投影/环境反光/正片叠底/全局色彩平衡
api:
  L11 contact_shadow(alpha,dx,dy,blur,strength)  # 要素1：柔边黑投影，15%-20% 不透明度（业界实测值）
  L23 env_reflection(fg,alpha,bg_tint,opacity)  # 要素2：环境反光——背景主色调染到前景，10%-15%，消除拼接感最关键一步
  L33 multiply_shade(dst,shadow)  # 要素3：正片叠底 C = A*B/255（加深接触阴影，非简单变暗）
  L38 global_grade(fg,bg)  # 要素4：顶层全局色彩平衡——前景色温/亮度向背景靠拢
  L48 bg_tint_of(bg,alpha)  # 取背景主色调（忽略极暗/极亮像素）
  L55 over(dst,src,a)  # Porter-Duff Over
internal:
  L5 _soft(alpha,k,r)
calls_in: contact_shadow→_soft, env_reflection→_soft
calls_out: alpha,bb,bg,cv2,dst,fb,fg,keep,np,px,sh,shadow,src
up: -
down: _build32
