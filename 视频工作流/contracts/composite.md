# composite 合成层契约

> 改本模块前必读：`IMPROVE_composite.md`（业界依据与历史 bug）

## 职责

把 AI 生成的序列帧资产合成到背景上，产出成片帧。
只做合成，不做物性计算、不做生图。

## 铁律

- **58** 合成必须 Porter-Duff Over、预乘 alpha、**线性空间**；
  多层严格**从远到近**，禁任意顺序 paste。顺序即结果。
- **59** AI 生成资产**禁以 chroma / flood_key 为主抠像**；
  必须走 matte（straight alpha / difference matting / RVM）。
  色键仅作兜底，且必须上报溢色风险。
- **60** 背景可控时优先 **Clean Plate + Difference Matting**；
  clean plate 由**代码生成并登记**，不得 AI 口头指定。
- **61** 镜头位移必须显式声明 `intent = travel | treadmill`；
  未声明**报错**，不默认。
- **62** 前景合成必须带**接触阴影**（alpha 腐蚀生成），否则禁止交付。

## 接口（代码真实签名）

```python
build_plate(fg, border=8)                    -> (plate, color)
difference_matte(fg, plate, softness=40.0)   -> alpha (H,W) float32
contact_shadow(alpha, dx=0, dy=8, blur=9)    -> shadow_alpha
porter_duff_over(dst_rgb, src_rgb, alpha)    -> rgb
composite_layers(bg_rgb, layers)             -> rgb   # layers 按 depth 升序（远→近）
```

`layer` = `{rgb, alpha, pos:(x,y), depth, contact:bool, shadow_dx, shadow_dy}`

## 自检要求

1. 证伪 Over **非交换性**：`A over B ≠ B over A`
2. `alpha=1` 完全替换、`alpha=0` 完全保留背景
3. `difference_matte` 对真实帧产出非全 0 alpha，前景占比 > 0.5%
4. matte 必须有**半透明边缘像素**（0.05<α<0.95 占比 > 0）
5. `contact_shadow` 非空
6. `composite_layers` 深度排序生效：远层先合、近层覆盖远层
7. 真实资产冒烟：旗帧合成到城墙背景，旗像素占比 > 0 且落位正确

## 依赖 / 被依赖

- 依赖: `numpy`、`cv2`（无本地业务依赖）
- 被依赖: `build_video`、`_scale_check`

## 改前必读

`IMPROVE_composite.md`
