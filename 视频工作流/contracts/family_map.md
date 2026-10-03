# 契约：族分类统一（铁律88）

## 问题
此前两套分类并存，AI 易搞混：
- driver.py: `biped/quadruped/vegetation/rigid/cloth`（物体类别）
- _solver_base: `cantilever/pendulum2/hinge/free_surface/chain`（物理形态）

## 铁律88：对外只有五类
**AI 只声明五类之一**，物理形态由代码查表转换，AI 不接触物理形态名。

## 映射表（唯一真源：_family_map.FAMILY_TO_PHYSICS）
| 五类 | 物理形态 | 说明 |
|---|---|---|
| biped | chain | 躯干驱动，四肢/衣摆为被动级 |
| quadruped | chain | 脊柱驱动，四腿相位交错 |
| vegetation | chain | 树干驱动，枝条受迫响应 |
| rigid | static | 刚体，无物理形变，只有位移+轮转 |
| cloth | chain | 受迫链（幡旗等） |

物理形态 `static` 为本契约新增，表示"不做振动求解"。

## 依赖/被依赖
- `_family_map` 依赖：无（纯数据+校验）
- 被依赖：`_solver_base`, `_solver_chain`, `driver`, `solver_survey`

## 改前必读
- `IMPROVE_family_map.md`：旧族遗留清单与迁移状态
- 改映射表前先确认 driver.FAMILIES 与 _solver_base.REQUIRED 同步

## 给 AI 的提示词（代码输出，非手抄）
```
[必做] 每个物体只声明"族"字段，值为五类之一
[禁止] 禁止填写 cantilever/pendulum2/chain 等物理形态名
[必做] 未知族会报错，不会静默降级
```
