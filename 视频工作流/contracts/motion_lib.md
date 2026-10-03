# motion_lib ·红 运动原子函数集(短名≤4字母)

接口: mj,fs,ip,w_ip,cadence_spm,L_EFF,slip,lipm,cp,mos,verlet,aero,spr,
      dmp,pnoise,add,walk_hip,HIP_FS
分族(选错会崩): 周期→fs/ip/slip｜点到点→mj｜被动物理→verlet/aero/pnoise
叠加用 add(加法非对冲)；动量层才是对冲(人体主动把净角动量压到0)
