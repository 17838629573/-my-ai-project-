# FILL param_decl   缺 3 槽位   （模型只填 pick，勿写散文）

## 决定 (decided)
已填: 无
  [IMPROVE:IMPROVE_param_decl.md:L20] 第一版用 `try: fake_require()` 假装验证"静默兜底会被抓"——假函数当然不会被任何机制抓到，检查是空转的。
  [IMPROVE:IMPROVE_param_decl.md:L25] → 自检必须用斜法向（1,1），用 (0,1) 会全零导致"单调性"测试假失败。
  [IMPROVE:IMPROVE_param_decl.md:L29] → 本模块用物理定义；若接引擎需另做映射，不可直接套用。
  [IMPROVE:IMPROVE_param_decl.md:L50] > 参数缺失，禁止心里默算。你必须：①联网检索权威取值 ②给出来源（文献/标准/厂商文档）
  [param_decl.py:L155] 1 缺失参数必须抛 AskAI，不是返回默认值
  pick: param_decl.py:155

## 收益 (achieve)
已填: 无
  [IMPROVE:IMPROVE_param_decl.md:L29] → 本模块用物理定义；若接引擎需另做映射，不可直接套用。
  [param_decl.py:L189] 7 合规参数能存能取且参与运算
  pick: IMPROVE_param_decl.md:29

## 代价 (accepting)
已填: 无
  [IMPROVE:IMPROVE_param_decl.md:L28] 物理平板 Cd≈1.28；但 NvCloth / Unreal 的 WindDrag 是 [0,1] 归一化美术参数，**不是同一个量**。
  [param_decl.py:L181] 6 越界 → 拒绝（防数量级错误）
  pick: IMPROVE_param_decl.md:28
