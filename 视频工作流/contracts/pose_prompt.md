# 契约：pose_prompt（轨迹 → 结构性提示词）

## 依赖 / 被依赖
- 依赖：`pose`（FK/IK/足端轨迹，唯一数值来源）、`constants`
- 被依赖：`build_video`、`character_sheet`

## 改前必读
`IMPROVE_pose_prompt.md`（真坑：关节角符号、左右脚判定、脚接触线）

## 铁律 73
**骨架图永不进画面。** 姿态只能以两种形式交给生图：
1. 结构性文本提示词（本模块，无 ControlNet 时的唯一解）
2. 条件控制图（仅当生图工具支持 control map 时）

禁止把骨架图当 reference image 喂图生图——模型会把它当画面内容照画。

## 铁律 74
提示词里的每一个姿态量都必须来自 `pose.solve()` 的输出，**禁止 AI 凭印象写
"抬腿""迈步"等模糊词**。代码算多少米，提示词就写多少米映射出的定性词。

## 铁律 75
走循环必须 **in-place + 脚接触线在格底**，相机固定。
（依据：Spriterrific 走循环受控提示词）

## 铁律 76
每帧提示词必须含**身份锁定段**，且与锚点图同源。

## 接口
```python
from pose_prompt import describe, sheet_prompts
txt = describe(joints, meta, gait, facing="right")
# -> "left foot planted forward, right foot pushing back behind,
#     right knee bent ~18°, arms counter-swing..."

prompts = sheet_prompts(spec, mode="walk", n=16)
# -> [{"i":0,"t":0.0,"phase":"l=stance r=swing","prompt":"..."}, ...]
```

## 业界依据
- Spriterrific：走循环 = 受控文本提示词 → 视频模型 → 抽帧成表，
  约束 in-place / 固定相机 / 交替步 / 手臂反相 / 身份锁定
- 帧数：walk 8–16 帧（spritesynth：walk 4–8 帧 @100–200ms），
  脚接触帧（contact frame）是卖出运动感的关键
- ControlNet OpenPose：骨架是 conditioning，不是被临摹的图像（本工具不支持）
