# character_sheet ·黄 角色图集+native/scaled两路径
史:notes/character_sheet.md

接口: SHEET, SUPPORTING, EXPRESSION, PROP, WALK_8FRAME, missing_assets,
      load_native, load_scaled, resolve, measure_native_composition,
      check_naming, tier_target_h, loop_closed
约束: native 禁止裁剪(会摧毁烘焙的头顶留白)
命名: char_anim_NN.png 全小写+下划线+帧号两位补零（不补零会静默重排）
分级: 占屏0.6+→1400｜0.4→1000｜0.2→700｜<0.2→420
注: 可动者登记已迁至 actors.py，本表只管贴图资产
