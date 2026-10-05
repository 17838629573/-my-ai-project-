# IMPROVE · _wall_geom.py 改前必读

Status: Accepted（2026-10-04）· Supersedes: 无

## 真坑（踩过，别重犯）

### 坑1：拆分时漏函数，连报两次错（我以为"切完了"）
拆出后第一次：`ImportError`（`wall_top_y` 切走了，但 `wall_depth_for_top` 漏在原地）。
补进去后第二次：`NameError`（它依赖 `y_at_depth`，那个 import 没跟着走）。
**两次都是在"我以为切完了"的状态下发生的。**

教训：拆分后必须 (a) 校验原文件所有 def 在新家可导入 (b) 跑一次真实调用。
手工切分脚本不校验就会漏——这正是该用 `split_mod` 类工具而不是手写的原因。

### 坑2：是【被迫拆出】，别合回 _surface.py
_surface.py 加 `_horizon_of` / `_path_center_x` 后达 373 行 / 13153 字符，超限。
禁提阈值，必须拆。

## 依据
- 项目铁律：体积超标 = 拆模块，禁止调高阈值

## 实测
拆后 `_surface` 338 行 / `_wall_geom` 59 行，均绿。
