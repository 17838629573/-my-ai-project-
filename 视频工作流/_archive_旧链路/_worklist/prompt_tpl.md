# FILL prompt_tpl   缺 3 槽位   （模型只填 pick，勿写散文）

## 处境 (context)
已填: 无
  [IMPROVE:IMPROVE_prompt_tpl.md:L41] **教训**：**只抛错不算防御**。注入假实现（补一个 biped）就能绕过单点校验，
  [IMPROVE:IMPROVE_prompt_tpl.md:L62] - `actors.py / build_video.py`：本片场景配置与输出路径，**允许**
  [IMPROVE:IMPROVE_prompt_tpl.md:L70] 2. `quadruped` / `rigid` 两族**只登记了族，驱动器未实现**
  pick: NEW: 生图提示词模板：把物理求解结果转成结构性姿态占位符

## 否决方案 (neglected)
已填: 无
  [prompt_tpl.py:L166] 【已修】setdefault 原在 _require 之后 —— 默认永远救不了缺槽，形同虚设。
  [prompt_tpl.py:L167] 默认必须在校验之前生效。
  [prompt_tpl.py:L198] 旧路径只给 t=0 单帧世界坐标 → 循环时足端从 1.5m 硬跳回 0，
  [prompt_tpl.py:L199] 观感即"只走出半步/动作断裂"。旧路径仅作无序列时的报错兜底。
  [prompt_tpl.py:L282] 5 biped 模板含结构性姿态占位符，而非模糊词
  pick: prompt_tpl.py:198

## 代价 (accepting)
已填: 无
  [IMPROVE:IMPROVE_prompt_tpl.md:L64] **改这块时别误把它们当污染清掉**——那是铁律37 允许/需要的示例。
  pick: IMPROVE_prompt_tpl.md:64
