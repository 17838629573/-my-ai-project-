[FACT] motion_lib   190行   机器生成，勿手改
doc: 运动原子函数集 Motion Atom Library
api:
  L26 mj(t,T,x0,x1)  # 最小急动度 (Flash&Hogan 1985). 起止速度/加速度均为0, 天然平滑.
  L35 fs(t,coef,w,n)  # 傅里叶级数. coef=[a0,a1,b1,a2,b2,...] 或 (a0,aj,bj 交替)
  L47 ip(th,l,g)  # 倒立摆角加速度. 小角度近似自然频率 w=sqrt(g/l), 人体步频落此附近(共振步态)
  L52 w_ip(l,g)  # 倒立摆自然频率. 注意: l必须用等效摆长(~0.3m), 不是腿全长(0.864m).
  L61 cadence_spm(l,g)  # 由等效摆长反推步频(步/分). 一步=半个振荡周期
  L67 slip(l,l0,k,c,dl)  # 弹簧倒立摆腿力(跑). F = k(l0-l) - c*dl
  L72 lipm(x,p,zc,g)  # 线性倒立摆水平加速度. 假设重心高度恒定(实际波动2-5cm)
  L77 cp(x,v,zc,g)  # 捕获点 XCoM = x + v/w. 超出支撑多边形必须迈步才能不倒
  L82 mos(xcom,cop)  # 稳定裕度. 越小越不稳, 可用于自动质检每一帧是否物理站得住
  L87 verlet(x,xo,a,dt,damp)  # Verlet积分. 速度隐含在(x-xo), 约束可直接改位置. 布料/头发/飘带
  L92 aero(v,n,A,rho,cd,cl)  # 空气动力. F = 0.5*rho*A*[(cd-cl)(v.n)*v + cl*|v|^2*n]  (CS184/Wi
  L104 spr(p1,p2,L0,k)  # 弹簧力向量(质点p1受p2). F = -k[(p1-p2) - L0*(p1-p2)/|p1-p2|]
  L113 dmp(v1,v2,kd)  # 阻尼力. F = kd*(v2-v1)
  L118 pnoise(t,seed,oct)  # Perlin风格风扰动(简化value noise). 用于随机风场, 增强不可压缩随机性
  L136 add(base,*offs)  # 附加层叠加(ADDITIVE, 非对冲). base=主运动, offs=局部偏移
  L152 walk_hip(t,w)  # 走路髋关节角(度). 系数来源: 下肢康复机器人论文, R^2≈1
calls_in: walk_hip→fs
calls_out: math
guard: return@L29, return@L97, return@L108
const: NAMES='\nmj    最小急动度五次多项式(点到点:坐/站/蹲/躺)  MJ(t,T,x0,x1)\nfs    傅里叶级数(周期:走/跑关节角)             FS(t,coef,w)\nip    倒立摆角加速度                            IP(th,l)\nslip  弹簧腿力(跑)                              SLIP(l,l0,k,c,dl)\nlipm  线性倒立摆水平加速度                      LIPM(x,p,zc)\ncp    捕获点XCoM(落脚点/稳定)                   CP(x,v,zc)\nmos   稳定裕度(质检)                            MOS(xcom,cop)\nverlet Verlet积分(布料/头发)                    VRL(x,xo,a,dt,damp)\naero  空气动力(风/衣摆)                         AERO(v,n,A,rho,cd,cl)\nspr   弹簧力                                    SPR(d,L0,k)\ndmp   阻尼力                                    DMP(v1,v2,kd)\npnoise Perlin风扰动                             PNOISE(t,seed)\nadd   附加层叠加(非对冲)                        ADD(base,*offs)\n', L_EFF=0.3, HIP_FS[7]
main: __main__@L157
up: -
down: -
