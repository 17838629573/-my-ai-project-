[FACT] composite   156行   机器生成，勿手改
api:
  L11 build_plate(fg,border)
  L18 difference_matte(fg,plate,softness)
  L37 contact_shadow(alpha,dx,dy,blur,strength)
  L60 porter_duff_over(dst,src,a)  # Porter-Duff source-over，线性光 + 预乘 alpha。
  L70 composite_layers(bg,layers)
  L91 self_check()
internal:
  L23 _erode(a,k)
  L30 _blur(a,r)
  L46 _srgb_to_lin(c)
  L53 _lin_to_srgb(x)
calls_in: contact_shadow→_blur, contact_shadow→_erode, porter_duff_over→_lin_to_srgb, porter_duff_over→_srgb_to_lin, composite_layers→_lin_to_srgb, composite_layers→_srgb_to_lin, composite_layers→contact_shadow, composite_layers→porter_duff_over, self_check→build_plate, self_check→composite_layers, self_check→contact_shadow, self_check→difference_matte, self_check→porter_duff_over
calls_out: Image,ImageFilter,L,bg,bgim,col,cv2,fg,np,o0,o1,os,out,plate,r1,r2,sh,z
guard: return@L24, return@L31
main: __main__@L154  self_check@L91
up: -
down: build_util,build_video
