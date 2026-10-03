# physics_rules ·红 物性推导与风力  史:notes/physics.md

常量: RHO_AIR=1.225, G=9.81, RHO_TISSUE=1000, V_REF=1.0
接口: volume_of, frontal_area, vogel_exponent, drag_force, accel,
      beaufort, raindrop_v, describe
公式: V=M/ρ → A=k·V^(2/3) → F=½ρv²CdA → a=F/m
柔性: F=½ρ·Cd·A·[v^(2+B)·V_REF^(-B)]，B<0（杨树-0.71/草-0.52/褐藻-0.93）
K_SHAPE: human4.12 animal4.61 cloth50 leaf31.8 tree8.0 object0.54
树干例外: 半径恒定 → S∝V^1.0（Galileo），用 trunk=True
风级: 蒲福 2级1.6-3.3树叶微响｜5级8-10.7小树摇摆｜7级13.9-17.1全树摇动
雨: v(D)=9.5(1-exp(-0.54·D^1.13))，D上限5-6mm，>6mm饱和9.0
铁律: 模型只填物性(M/ρ/kind/Cd/B)，面积与运动一律代码算
