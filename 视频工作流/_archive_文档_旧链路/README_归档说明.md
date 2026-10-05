# _archive_文档_旧链路 —— 归档说明

**本目录内 37 份文档全部描述旧链路，与现行引擎无关。请勿依据这些文档改代码。**

## 为什么归档

2026-10-05 全量核对发现：

| 项 | 事实 |
|---|---|
| 旧 README 声称的 `WORKFLOW.md` | **不存在** |
| 旧 README 声称的 `contracts/`（50 份契约） | **不存在** |
| 旧 README 声称的 `params_ai.json` | **不存在** |
| 旧 README 声称的 `gate_*.py`（三道门禁） | **不存在** |
| 旧 README 声称的"GrabCut 抠像 + 生图"流程 | **现行引擎是 SDF 程序化渲染，无生图环节** |

旧 README 描述的是"自然语言 → 生图提示词 → 出图 → 抠像合成"的管线。
现行引擎是"骨架 → 胶囊 SDF → 光栅化 → mp4"的**程序化动画管线**，两者不是同一条路。

## 归档内容

- `README_旧链路.md` —— 旧 README 原文
- `IMPROVE_*.md` 共 36 份 —— 对应项目根目录 36 个 `.py`

## 这 36 个 py 均为孤立代码

用 `_proc/tools/reach.py` 从 5 个活跃入口出发做可达性分析：

```
活跃入口  5 个    _proc/beat_demo.py, _proc/motion/cafe.py,
                  _proc/tests/run_all.py, _proc/check.py, _proc/gen_index.py
可达文件 49 个
孤立文件 47 个   ← 根目录 36 个 py 全部在内
```

**判定依据是可达性分析，不是眼估。** 根目录这 36 个 py 没有任何活跃入口引用它们。

## 文档行数核对（归档前实测）

36 份 IMPROVE 文档中：

```
行数与代码一致   19 份
行数已漂移        7 份  _common 238→282, _surface 311→337,
                        environment 169→222, path_align 127→159,
                        _layer_style 58→59, systems_phys 149→150,
                        systems_view 149→153
文档未标行数     10 份
```

即：文档本身也停止维护了，存在漂移。

## 现行文档在哪

- **项目总纲** —— `/README.md`（重写版，与代码一一对应）
- **三层契约图** —— `_proc/INDEX.md`（由 `gen_index.py` 从各文件顶部契约块自动生成，不会与代码脱节）
- **对照报告** —— `文档代码对照报告.md`（记录本次核对发现的全部不一致）
