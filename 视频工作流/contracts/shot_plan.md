# 契约 · shot_plan（镜头规划 / 生图任务包）

层: L2（编排）  依赖: path placement scale_map wind_sway groundline
被依赖: build_video

改前必读: IMPROVE_shot_plan.md

---

## 职责边界

**只做规划，不画像素。** 输出一份「生图任务包」，告诉 AI：
背景图上路该怎么画、每个物体该多大、该落在哪、提示词怎么写。

不负责：生图本身、合成、播放。

## 接口

- `plan_shot(bg_shape, spec, placements) -> dict`
  返回 `{path_hint, objects, prompts}`：
  - `path_hint`：路径在背景图上的像素控制点 + 可通行半宽 + 长度
  - `objects`：逐物体 `{name, target_px, anchor_px, semantic_point}`
  - `prompts`：逐物体生图提示块文本（含米制、比例、路径）

- `path_prompt(path_hint) -> str`
  给「背景图」的提示词：路从哪到哪、多宽、什么材质。

## 铁律

- **T83 生图必须带路径提示**：背景图的路画在 `path_hint` 给的坐标上，
  AI 不得凭印象另画一条。否则运行时角色会走在路上但图上没有路。
- **T84 落位坐标由 placement 算出，不手填**：`anchor_px` 一律来自
  `placement.semantic_point`，禁止 `sc.get("baseline_y", 780)` 这类兜底。
- **T85 任务包必须含米制描述**：每个物体提示词带真实米数，
  对抗生图模型无内在尺度感的问题。

## 依赖 / 被依赖

依赖: path, placement, scale_map, wind_sway, groundline
被依赖: build_video
