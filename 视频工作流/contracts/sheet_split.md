# sheet_split — 图集切分契约

## 业界依据（本轮搜证）

| 来源 | 权威 | 要点 |
|---|---|---|
| agent-sprite-forge `split_grid()` | 低（但实现最完整） | 网格裁剪→trim_border(4px)→clean_edges(3层)→连通域→选bbox→shared_scale→对齐 |
| besthub《GPT-Images 精灵指南》 | 中 | **AI 图集必然溢出**：按格硬切会切掉脚、帽檐溢进邻帧；修法=整图连通域→映射回预期格序；每帧单独去背景；**共享锚点** |
| TexturePacker | **极高** | Grid 算法=等距网格；Trimming 须有数据文件记录裁掉量；Polygon 移除透明 |
| codestudy 连通域法 | 中 | alpha>阈值→8向连通域→min_area 滤噪点→按 area 排序 |

## 铁律44：图集切分 = 网格定序 + 连通域定界，禁纯硬切

**纯硬切（现状 `_split_sheet.py`）的失败模式**（besthub 原文）：
> Poses overflow the cell boundaries. Simple cell cropping cuts off feet and lets hat edges bleed into the next frame.

即：姿态溢出格子 → 硬切切掉脚 / 邻帧内容渗进来。

## 流程（8 步，顺序不可换）

```
1. 网格定位     按 (cols,rows) 取格，得预期顺序与期望帧数 N
2. trim_border  每格四边各裁 4px      ← 去除相邻格共享的抗锯齿接缝
3. clean_edges  从边缘向内扫 3 层，擦 暗色(r,g,b<40) / 近键控色(dist<150) 残边
4. 连通域       8 向 BFS，字段 {area, bbox, touches_edge}，按 area 降序
5. touches_edge 校验 ← 触边=溢出/被邻帧污染，必须报错不留过
6. 映射回格序   按 bbox 中心落在哪个格 → 归入该格；一格多组件取最大
7. shared_scale 先求所有帧 max(w,h)，导出【单一】缩放因子  ← 防各帧大小不一
8. shared_anchor 统一 bottom-Y（脚在同一像素）+ center-X   ← 防漂移
```

## 硬性校验（任一 FAIL 即报错，禁静默）

| 项 | 判据 |
|---|---|
| 组件数 | ≥ 期望帧数 N，少一个即报错（说明有帧没生成） |
| touches_edge | 任一组件的 bbox 触格边 → 报错（溢出） |
| min_area | < 10 px 视为噪点丢弃；丢弃后不足 N 报错 |
| 尺寸一致性 | shared_scale 后各帧画布尺寸必须完全一致 |
| 锚点 | 各帧 bottom-Y 必须相同（±1px） |

## 与既有铁律的关系

- 铁律41（素材张数由代码算）→ 本契约的"期望帧数 N"来源
- 铁律40（修订：一物体=一组图集，共用同一身份参考图）→ 本契约输入为一组图集中的一张
- chroma.py 已做最大连通域去噪（clean_mask），本契约第 4 步**复用**它，不重写

## 待验证

`shared_anchor` 对幡旗类物体（杆顶固定而非脚底固定）应为 **top-Y** 而非 bottom-Y。
锚点类型应由 AI 在 spec 中声明（`anchor_edge: "bottom"|"top"`），默认 bottom。
