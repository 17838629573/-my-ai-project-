# FILL build_video   缺 3 槽位   （模型只填 pick，勿写散文）

## 决定 (decided)
已填: 无
  [IMPROVE:IMPROVE_build_video.md:L11] 真实物体应是「主体竖直（重力方向）+ 横向小幅摆动偏移」，
  [IMPROVE:IMPROVE_build_video.md:L15] **B. 三人共用一套序列帧**
  [IMPROVE:IMPROVE_build_video.md:L16] 慧琳、石槃陀直接复用玄奘图集，仅相位错开 0.13s，服饰/体型无差异。
  [IMPROVE:IMPROVE_build_video.md:L17] 业界解法：Modular Atlas（body base + 服饰 overlay 分层合成）或换色图生图。
  [IMPROVE:IMPROVE_build_video.md:L24] 旗 (219,49,128)、玄奘 (185,50,100) 玫红。已用 `chroma_key(ref=None)` 自动取四角色抠像
  pick: IMPROVE_build_video.md:11

## 收益 (achieve)
已填: 无
  [IMPROVE:IMPROVE_build_video.md:L47] > 不得让代码静默跳过。树为可选，缺失可以不画但要打印明示。
  pick: IMPROVE_build_video.md:47

## 代价 (accepting)
已填: 无
  [IMPROVE:IMPROVE_build_video.md:L12] 现在是整条链在空间中大幅旋转 → 生成图形态随相位大幅变化 → 帧间一致性差。
  [IMPROVE:IMPROVE_build_video.md:L16] 慧琳、石槃陀直接复用玄奘图集，仅相位错开 0.13s，服饰/体型无差异。
  [IMPROVE:IMPROVE_build_video.md:L28] 成片体检用「与背景差分 + 阈值 120」：mp4v 有损压缩会引入全画面噪声，阈值 40 会误判。
  [IMPROVE:IMPROVE_build_video.md:L42] - 树缺图 → 非致命，但**必须打印明示**，禁静默跳过
  [IMPROVE:IMPROVE_build_video.md:L47] > 不得让代码静默跳过。树为可选，缺失可以不画但要打印明示。
  pick: IMPROVE_build_video.md:16
