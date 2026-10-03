# groundline · 地基线探测

**职责一句话**：从背景图自动找出"人可以站在哪条水平线上"，输出 baseline_y。

## 依赖 / 被依赖

- 依赖: (无本地依赖，只用 numpy/PIL)
- 被依赖: build_video, scale_map

## 改前必读

`IMPROVE_groundline.md` ← 真坑与待办，改这块前必读

## 接口（真实签名）

```python
detect(bgr, band_px=24, top_n=8, y_range=None) -> dict
    # 返回 {baseline_y, confidence, candidates:[{y,strength,contrast,score}], evidence}
    # y_range=(y0,y1) 限定搜索行范围；None 表示全图
probe(bgr, y) -> dict
    # 返回指定行的 {contrast, above_rgb, below_rgb}，供 AI 复核某条候选
self_check() -> int
```

## 铁律

**铁律67：baseline 必须由背景图探测得出，禁止手填像素**
手填的 baseline 会让人站在墙体内部、旗插进墙里，且代码无从发现。

## 业界依据（真联网搜得）

| 来源 | 要点 |
|---|---|
| pixel-monkey《Perspective and Scale》 | 地平线法则：相机视平线穿越所有同高物体的同一相对点；隐藏地平线由汇聚平行线的消失点求出 |
| Simon et al.(VP-independent) | 水平线段在视平线高度**聚集**——对其 y 坐标做直方图，峰值即地平线 |
| ODU《Vision-Based Safe Landing》 | 大 σ 高斯低通去细边 → Canny 提主边 → 强度 top p% → Hough 拟合 → 比较**双侧窄带**平均强度选真峰 |
| Cornall et al. | 天空/地面**颜色分布差异**分割求地线 |

## 实现要点（对应业界）

1. 高斯低通（σ 自适应 = 行数/50）去砖缝等细边 —— ODU
2. Sobel-y 求水平边缘，按行累加得行强度直方图 —— Simon et al.
3. 非极大抑制取 top-N 候选行
4. 每候选算**双侧窄带颜色对比度**（上带 vs 下带），砖缝两侧同色 → 对比度低；墙顶上下（天空 vs 墙） → 高 —— Cornall et al. + ODU 双侧窄带思想
5. score = 归一化强度 × 归一化对比度，取最高分为 baseline

**为何用颜色对比度而非纯边缘强度**：城墙的砖缝也有强边缘，但两侧颜色几乎相同，纯强度会把砖缝误判成地线。
