# 契约：_perspective（透视几何）

## 依赖
- 仅 stdlib（math）。无业务依赖。

## 被依赖
- 路径生成（长城纵深走向）
- scale_map 的纵深维度（当前只有单一 px_per_m，待接入）
- 生图提示词：物体像素高、地平线约束

## 铁律
- **100** 路径点必须由 `y_at_depth` / `path_along_depth` 函数生成，**禁手填两点坐标**
- **101** 横向（平行画面）移动 scale 恒定；纵深移动 scale 随 (y−v_h) 线性变
- **102** 相机高度 H_cam 由参照物经 `camera_height_from_ref` 反解，禁手填
- **103** 地平线由 `horizon_from_vanishing` 探测，交点不足须报错（铁律31）

## 接口
```
focal_px(image_h, ratio=1.4)                      -> float
horizon_from_vanishing(segs, image_h)             -> float
camera_height_from_ref(y_world, v_t, v_b, v_h)    -> float
scale_field(y, v_h, h_cam)                        -> float
depth_at(y, v_h, f_px, h_cam)                     -> float
y_at_depth(z, v_h, f_px, h_cam)                   -> float
path_along_depth(z0, z1, n, v_h, f_px, h_cam, x_of=None) -> [(x,y,scale)]
path_lateral(y, x0, x1, n, v_h, h_cam)            -> [(x,y,scale)]
object_px_height(y_world, y_base, v_h, h_cam)     -> float
```

## 改前必读
- `IMPROVE_perspective.md`（业界依据：Hoiem IJCV2008 / CVPR Scale Field / 地面平面测距）
- 唯一常数 `F_OVER_IMAGE_H=1.4`，出处 Hoiem 正文，改动须换来源
