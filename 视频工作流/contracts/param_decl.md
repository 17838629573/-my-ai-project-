# 契约：param_decl（参数声明与反问接口）

## 依赖 / 被依赖

- 依赖：`json` `os` `ast`（标准库，无业务依赖）
- 被依赖：`cloth_aero`、`_common`、任何需要外部物性参数的模块
- 数据文件：`params_ai.json`（AI 作答落盘处）

## 改前必读

- `IMPROVE_param_decl.md` ← 业界依据、踩过的坑、待办
- 改 `require()` 前须知：禁止引入任何"返回数字常量"的兜底路径（自检证伪A 会 AST 扫描拦截）

## 对外 API

| 函数 | 作用 |
|---|---|
| `require(name, family, why, unit, hint)` | 取参数；缺失抛 `AskAI`，不合规抛 `ParamRejected` |
| `have(name)` | 是否已声明 |
| `save(name, value, unit, source, range, family)` | 落盘（写入前先验） |
| `verify(entry)` | 五项字段校验：value 数值、source 非空、range lo<hi 且 value 在区间内 |
| `audit()` | 列出全部已声明参数 |

## 铁律

- **99**：缺失参数禁止默算/兜底，必须反问 AI
- **100**：无来源引用拒绝（防幻觉）
- **101**：必须带合理区间，越界拒绝
