# actors ·红 可动者登记+能力白名单+硬报错

铁律: 分类按【能不能动】，不按【是不是人】
  能动(人/动物/植物/门/旗/水/火) → actor，必须能被代码驱动
  动不了(城池/房屋/地形/远山)     → 背景，静态整图
背景图只允许烘焙"动不了"的东西；可动件必须单独成层

接口: ACTORS, CAPABILITY, BG_STATIC, require(action,actor),
      check_shot(name,decl), missing_actor_assets()
三态(Unity官方): static不动｜kinematic代码驱动(走路主角/推门)｜dynamic物理求解(旗/叶/布)
kind: human/animal/plant/object/cloth/fluid/tree/leaf（定 K_SHAPE 的 k）
物性字段: body_type, mass(kg), rho, cd, b_vogel —— 面积由代码算，禁手填
校验: check_body_type() 三态合法性
role: protagonist/supporting/movable
CAPABILITY.impl=None → HALT 硬停机，禁止降级与占位
判定: python3 actors.py（自带5项自检）
