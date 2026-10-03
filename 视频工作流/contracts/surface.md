# 契约：_surface.py 表面与放置

## 依赖
_perspective.py（透视）、param_decl.py（缺参数反问）

## 被依赖
（待接入）shot_plan.py / scale_map.py / character_sheet.py / path_align.py

## 铁律 104-106
104. 物体落点由「表面类别 + 透视」算出，禁手填屏幕坐标。
105. 墙高、地面等物理量须由 AI 搜证落盘（param_decl），代码反问不许凭印象给。
106. 墙顶/落点跑出画面必须报错，禁给负值、禁裁到边界了事。

## 接口
- SURFACE_CLASSES: sky/far/wall_face/wall_top/path/soil
- NORMAL: 各面法线（wall_face 水平、其余朝上）
- RULES: 种类→允许表面+排除区（tree 只 soil 且排除 path）
- surface_at(y, v_h, y_wall_base) → 表面类别
- ground_y_at_depth(z,...) / wall_top_y(h,z,...,image_h)
- wall_depth_for_top(h_wall, y_top_target, ...) → 反解墙深（取代手填 z）
- offset_outside_path(...) → 树等退让到路缘外 clear_m
- place(kind, ...) → {'surface','x','y','via'}

## 改前必读
IMPROVE_surface.md
