# 契约块：solver（唯一起算入口）

**状态**：黄（有契约 + 有 self_check + 自检PASS）

## 职责

AI 只做两件事：**搜索物性**、**调度生图**。中间所有算术由本模块完成。

```
AI 搜物性 ──spec──> solver.solve() ──答案包──> AI 拿去生图 ──图──> 代码播放
```

## 边界（代码不代替 AI 强项）

| 归谁 | 内容 |
|---|---|
| **AI 填** | family、几何尺寸、材料物性（σ/ρ/E/t）、风速 |
| **AI 判** | family（悬臂/铰链/液面…）语义分类 |
| **代码留** | 普适常数（标源） |
| **代码算** | 质量、面积、无量纲数、regime、频率、周期、帧数、物理点 |

## 接口

```python
solve(spec) -> {
  "derived":  {mass_kg, area_m2, B_nm2},
  "dimensionless": {R1, R2, Re, Fr, Ustar},
  "regime": "flapping",
  "freq_hz": 1.708, "period_s": 0.585,
  "frames": 35,          # = round(T*FPS)，铁律29
  "mat_frames": 35,      # 素材张数 = round(T*FPS)，【铁律54】视频不封顶
  "playrate": 1.0,
  "points": [(s, A/Amax, lag_deg), ...],
  "phase_geometry": [[(x,y), ...], ...],
  "draw": {...}, "sheet": {"rows":4,"cols":4,"count":16,"phase_map":[...]},
}
```

**【铁律41】** `solve()` 与 `--run` 输出必须含：`mat_frames`、`sheet.rows/cols`、`sheet_plan()`、`sheet.phase_map`、`playrate`。
代码算了却不发出来 = 等于没算（铁律33 的具体化）。

## 硬约束

1. **缺槽即报错**，绝不静默填默认值（铁律31）
2. **帧数 `N = round(T×FPS)`**，禁手填（铁律29）
3. **St 定义 `St = 2A·f/U`**，禁混用 `f·L/U`（铁律20，差 1.60 倍）
4. 物理点固定端位移恒为 0
5. 公式只在 physics/anchor/framerate 实现一次，本模块只编排

## 族

- `chain`：部分动部分不动（树干→枝条、头皮→发丝、肩腰→衣摆）。不新建族，只推广。
- `transient`：冲击波/突然大风，瞬态衰减解。
- 其余族分派见 `contracts/driver.md`。

## 依赖

`physics`、`anchor`、`framerate`

## 被依赖

`solver_check`、`build_video`、`pipeline/*`

## 改前必读

**`IMPROVE_solver.md`** —— 普适常数表（含来源）、chain 四公式、transient 解、
briefing_text 入口清单、铁律41 理由、历史踩坑。改本模块前必读。

## 自检

`python3 solver.py` → 40 项自检（含 chain/transient/briefing/容纳/探针）
