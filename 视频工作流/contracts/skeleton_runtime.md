# skeleton_runtime ·黄 Spine解析+FK+slot排序防穿模
史:notes/skeleton_runtime.md

接口: mat_mul/mat_local/mat_apply/mat_inverse,
      Skeleton(data,img_loader).world_matrix/.draw/.pose/.unknown,
      apply_animation, check_driven
槽位序: legL→legR→armL→armR→torso→head（索引大者在上）
骨骼: root/hip/torso/head/legL/legR/armL/armR（8根；无膝踝）
必跑: 改骨架后 check_driven(sk,驱动名)，返回空才通过
