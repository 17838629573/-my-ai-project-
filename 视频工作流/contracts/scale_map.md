# scale_map — 比例尺层

## 依赖 / 被依赖

- 依赖: `math`, `constants`(无)
- 被依赖: `solver`(问卷输出), `composite`(落位 resize), `solver_check`
- 禁止: 被 `pipeline/sheet_pack` 反向依赖

## 改前必读

`IMPROVE_scale_map.md` ← 真坑与待办，改这块先读它

## 职责一句话

把「米」换算成「像素」，并强制所有部件对**同一个命名参照物**取尺度。

（一句话不含 and → 内聚合格）

## 业界依据（联网搜证，非自造）

| 依据 | 来源 | 落地 |
|---|---|---|
| 图集交付必含 **pixels per unit** 导入说明 | Sprite Sheet Maker Workflow | `px_per_m` 为一级输出 |
| 锁定尺度用 **named reference object**，每次都对它缩放，不靠肉眼、不对上一个资产缩放 | Scale drift 治理业界共识 | `reference` 唯一，其余全部由它推 |
| **AI 无内在尺度感**，须显式注入米制参照与命名参照物 | floniks / Perspective Research Centre | `prompt_block()` 必须含米制描述 |
| **Baseline 锁定**（feet on y=82）防角色意外弹跳 | Sprite Sheet Maker 交付清单 | `baseline_y` 全局共用 |
| **Pivot 规则**（bottom center）防脚/武器跳动 | 同上 | `pivot` 决定 resize 后的落位原点 |
| 尺度正确后才能谈任何后续测量 | 业界测量流程 | `verify()` 在合成前拦截 |

## 接口

```
build_scale_map(scene) -> dict
    scene 必填槽（缺即报错，铁律31）:
      canvas      {w_px, h_px}
      reference   {name, real_m, px}        ← 命名参照物，唯一
      baseline_y  int                        ← 地平线，站立物共用
      objects     [{name, real_m, pivot, on_ground, anchor_y_px?}]
    返回: px_per_m / 每物体 target_px / target_box / placement / prompt_block

verify(smap, measured) -> (ok, report)
    AI 量出资产实际像素高 → 代码比对 target_px
    偏差超阈值即 FAIL，合成前拦截

prompt_block(smap) -> str
    给生图用的米制描述块，含命名参照物 + 倍数关系 + 地平线
```

## 铁律

- **63**: 一个场景只有一个命名参照物，其余部件全部由它推像素尺寸，禁止各自估
- **64**: 合成前必须 `verify()`，偏差超阈值不许落位
- **65**: 生图提示必须含 `prompt_block()` 的米制描述，禁只写形容词
- **66**: 站立物共用 `baseline_y`，禁止各画各的地平线
