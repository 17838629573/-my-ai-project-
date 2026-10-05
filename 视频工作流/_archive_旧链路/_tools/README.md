# _tools —— 工作流维护工具集（独立于工作流）

> 定位：这些是**维护工作流的工具**，不是工作流的一部分。
> 不依赖业务语义，可移植到任何 Python 项目。工作流本体在上级目录。

## 用法（全部在 `_tools/` 下运行）

| 命令 | 作用 |
|---|---|
| `python3 depgraph.py` | 重生成 `deps.md` + `deps.mmd`（依赖图） |
| `python3 depgraph.py --check` | **漂移校验**：图与源码不符则退出码 1 |
| `python3 depgraph.py --cycles` | 列循环依赖 |
| `python3 depgraph.py --layers` | 列跨大模块依赖 |
| `python3 contract_gen.py` | AST → `contracts/`(定位) + `detail/`(事实) |
| `python3 undef_check.py` | 漏 import / 未定义名全仓扫描 |
| `python3 impact.py <模块>` | 改动下游分析，`--check` 实跑自检 |
| `python3 doc_lint.py` | 文档结构化门禁（散文检测） |
| `python3 doc_triage.py` | 散文分诊（WHY/REDOABLE/META/FILLER） |
| `python3 why_struct.py` | Y-Statement 七槽位覆盖率 |
| `python3 why_fill.py` | 生成补槽位工作单（工具检索，模型只填 pick） |
| `python3 why_apply.py` | 回填工作单 → `IMPROVE_*.md` |
| `python3 why_gen.py` | 生成 why 层桩（不覆盖已有） |
| `python3 m_<L>_<M>.py` | 28 个中模块 facade，聚合跑组内自检 |

## 分层职责（勿混）

```
contracts/<m>.md   定位层：内部大概做什么 + 大类 + api 名
detail/<m>.md      事实层：行号/签名/调用/常量（机器翻译）
IMPROVE_<m>.md     why 层：依据/坑/意图（人写，机器从不覆盖）
```

事实层禁止手写；why 层禁止机器生成。

## 设计铁律

1. **工具优先**：能形式化为规则的先写工具，工具做不了才由模型动手
2. **模型只填 pick**：`why_fill` 生成候选句，`why_apply` 回填 —— 模型不写散文
3. **事实可证伪**：契约里的事实必须能被代码证伪，否则会漂移成谎言
4. **改代码必重生成**：改 import → `depgraph.py`；改结构 → `contract_gen.py`

## 当前状态（2026-10-03）

```
工作流: 106 模块 / 239 边 / 0 真环       依赖图 PASS（无漂移）
未定义名: 0                              undef_check PASS
契约  : contracts 142 份 41349 字符      门禁 PASS
事实  : detail 107 份 68148 字符
enforce validate: 1 项（_build32 资产缺失）
```

## 环的口径（重要）

`find_cycle` 必须基于**静态图**（剔除 `[runtime]` 边）。懒加载与
`__main__` 守卫内的 import 在模块被 import 时不执行，**不构成真环**。
本仓库 7 个"环"全是这类假阳性，已修正：

- `depgraph.py`：懒加载边以 `[runtime]` 标注写入 `deps.md`
- `enforce.py`：新增 `static_deps()` 剔除 runtime 边
- `enforce_cmds.py`：两处 `find_cycle` 改用 `static_deps(deps, runtime)`

## 工具出错记录（工具建议须验证）

1. 建议 `from driver import EXAMPLES` → 实为 `solver_survey`（list vs dict，跑了才暴露）
2. 建议 `import numpy` → 实需 `import numpy as np`（代码用 `np.`）

结论：工具能精确定位，但**类型/别名兼容性它判不了**，改完必须实跑验证。

## 已归档

`deps_sync.py` → `_archive/`（功能被 `depgraph.py` 取代，避免两套抢写 `deps.md`）
