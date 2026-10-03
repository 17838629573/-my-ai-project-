# IMPROVE · placement（改这块前必读）

## 本模块要解决的问题

「一个东西该放在画面哪里」——旗插墙头、人站走道、车放墙顶、树栽地面。
此前 `build_video.py` 直接 `baseline_y - rgb.shape[0]`，等价于**用图像顶部当锚**，
且 `baseline_y` 手填 780（墙体内部），导致旗插进墙里、人贴着墙面走。

## 真坑（踩过的）

### 坑1：逐帧自动居中是错的（业界明确禁止）

上一轮为修「跨帧漂移 269px」，用了**逐帧居中对齐**。
那是 auto-centering。framesprite.com 原话：

> Auto-centering each trimmed visible rectangle creates a different semantic
> point even when every normalized value is 0.5.

即：每帧裁剪矩形大小不同 → 各自的 0.5 中心指向源画布的不同位置。
自检第 10 项做了证伪：**矩形中心对齐时，接地点偏离目标 160 px**；
而固定语义点做法是 0.00e+00。

**修法**：固定源画布尺寸 + 每帧复用同一 regpoint + 记录 trim offset。

### 坑2：接地点 ≠ 最低 alpha 像素

gamedev.stackexchange 原话：跑步序列有帧双脚离地；角色也可能与地面相交。
接地点是**设计出来的接触点**，不是量出来的最低点。
所以 `ground_contact` 用画布底边中心，不做图像测量。

### 坑3：自检自身假 PASS（本模块内出现过）

第 7b 项初版写成 `ck("对照:auto-centering有定义差", True, ...)` ——
永远 PASS，什么都没验。已改成真正的证伪（测底边偏离量）。
**这是本项目第 6 次遇到自检假 PASS。**

## 待办（还没做）

- [ ] `build_video.py` 仍未调用 placement：`baseline_y - rgb.shape[0]` 还在
      （第一行 `baseline_y = sc.get("baseline_y", 780)` 也是手填兜底）
- [ ] `groundline.detect()` 已存在但 `build_video` 零调用 —— baseline 仍手填
- [ ] `_split_sheet.py` 切图后未输出 trim offset，placement 的 trim 通道尚无真实数据喂入
- [ ] 汽车/挂件类 `attach` 语义点的 ratio 尚无 AI 声明入口

## 依赖方向（改动时注意）

```
placement (L0, 无本地依赖)
    ↑ 被 build_video / composite / scale_map 依赖
```
不要在 placement 里 import 任何本地模块，否则成环。

---

## 业界依据（真联网搜得，从 contracts/placement.md 剥离）

| 来源 | 要点 |
|---|---|
| framesprite.com《Sprite pivot, anchor and origin》 | 先命名语义点（质心/底部中心接地/武器握把/附着点），再转各引擎单位；默认 center 不自动正确 |
| 同上 | 归一化 0.5 不代表一致——裁剪矩形不同则指向不同源位置；图集元数据必须恢复源尺寸与偏移 |
| 同上 | 固定外画布使像素可比：360×360 画布中心恒为 180×180，即使可见宽度 145→189 |
| gamedev.stackexchange | 逻辑原点 = 精灵触地处 + 水平中心，对所有精灵恒定；不必是最低像素，也不必是实际中心（长矛骑士的水平中心可偏左） |
| 同上 | 视觉原点应与碰撞/事件坐标分开记录 |
| TexturePacker | Pivot point editor 逐帧对齐 + 实时预览 |

**铁律73 业界原话**："Auto-centering each trimmed visible rectangle creates a
different semantic point even when every normalized value is 0.5."
