# enforce ·绿 门禁（唯一裁判）

  check-contract <模块>   模块是否已在 deps.md 声明
  check-deps             依赖无环 + 被依赖文件真实存在
  check-assets           资产硬阻断(actor/背景/前景占比)
  check-evidence <码>    判定须附退出码与依据
  gate <kind> <stage>    Stage 过门
  validate               以上全部

铁律: 判定必须带命令输出，禁止"应该没问题"
