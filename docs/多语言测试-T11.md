# FastAPI Full-Stack Template —— 多语言混合项目健壮性补充测试

> 测试方向：**多语言混合 + 前后端分离 + 部署配置**（前序 T1-T10 未覆盖）  
> 项目来源：真实开源项目 https://github.com/fastapi/full-stack-fastapi-template  
> Stars：43.2k  
> 技术栈：Python（FastAPI）+ TypeScript/React + PostgreSQL + Docker  
> 测试日期：2026-09-08  
> 工作流版本：通用模块化 AI 编程工作流 v5

---

## 一、测试目标

前序健壮性测试（v5 ROBUSTNESS）已覆盖：权限闭环、工具缺失、依赖缺失、契约不一致、红区保护、超时、凭证、磁盘等 10 个场景，全部通过。

**本次补充测试聚焦以下未被覆盖的方向：**

1. **多语言混合项目**：工作流能否正确识别并拆分含多种语言（Python + TypeScript）的项目？
2. **前后端分离架构**：deps.md 契约图如何处理跨语言/跨进程的依赖关系？
3. **部署与配置红区**：Docker Compose、.env、CI/CD 配置是否被正确识别为红区？
4. **规模判断与多层递归**：全栈项目是否需要多层架构师拆分？
5. **数据库 Schema 依赖**：SQL 模型与代码之间的契约如何体现？

---

## 二、项目结构（真实）

```
full-stack-fastapi-template/
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic/              # 数据库迁移脚本（SQL）
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI 入口
│   │   ├── api/              # API 路由层
│   │   │   ├── deps.py       # 依赖注入
│   │   │   └── routes/
│   │   │       ├── login.py
│   │   │       ├── users.py
│   │   │       └── items.py
│   │   ├── core/             # 核心配置
│   │   │   ├── config.py     # Pydantic Settings
│   │   │   └── security.py   # JWT/密码哈希
│   │   ├── models/           # SQLModel 数据库模型
│   │   │   ├── user.py
│   │   │   └── item.py
│   │   ├── crud/             # 数据库 CRUD 操作
│   │   │   ├── user.py
│   │   │   └── item.py
│   │   ├── schemas/          # Pydantic 数据校验模型
│   │   │   ├── user.py
│   │   │   └── item.py
│   │   ├── tests/            # Pytest 测试
│   │   └── utils/            # 通用工具
│   └── prestart.sh           # 启动前脚本
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── src/
│   │   ├── main.tsx          # React 入口
│   │   ├── routes/           # 路由组件
│   │   ├── components/       # UI 组件
│   │   ├── hooks/            # React Hooks
│   │   ├── client/           # 自动生成的 API 客户端
│   │   └── lib/              # 工具函数
│   └── index.html
│
├── docker-compose.yml        # Docker 编排
├── .env                      # 环境变量（红区）
├── .github/
│   └── workflows/            # CI/CD（红区）
└── README.md
```

---

## 三、工作流执行过程

### 步骤 1｜接需求 + 多语言识别

**需求复述**：FastAPI Full-Stack Template 是一个生产级全栈 Web 应用模板，提供开箱即用的用户认证、CRUD 管理、Docker 部署能力。

**核心功能点**：
1. JWT 认证 + 密码找回（后端 FastAPI）
2. 管理后台 CRUD（前端 React + TypeScript）
3. 数据库 ORM + 迁移（SQLModel + Alembic）
4. 自动生成前端 API 客户端（OpenAPI → TypeScript）
5. Docker Compose 一键部署（开发/生产环境）

**多语言识别**：工作流正确识别出 **3 种技术语言/领域**：
- Python（后端业务逻辑）
- TypeScript/React（前端交互）
- SQL（数据库模型 + Alembic 迁移脚本）
- 外加部署领域：Docker Compose、GitHub Actions CI/CD

**规模判断**：
- 文件数：~80 个代码文件（前后端合计）
- 模块边界：前后端物理分离（backend/ vs frontend/），但**通过 API 契约耦合**
- 判定：**中等规模，但建议双层拆分**——顶层按"前后端+部署"拆分，各自内部再按职责拆分

---

### 步骤 2｜拆模块（多语言混合的挑战）

#### 挑战 1：跨语言依赖如何表达？

传统 deps.md 假设所有模块都是同一种语言内的 import 关系。但全栈项目中：
- 前端 `src/client/` 里的 TypeScript 代码**不是 import 后端 Python 代码**
- 而是通过 **HTTP API + OpenAPI Schema** 间接依赖
- 这种依赖是**运行时契约**，不是编译时依赖

**工作流的应对**：
- deps.md 中增加 **「跨进程契约」标注**：`frontend/client -> backend/api (HTTP/OpenAPI)`
- 说明依赖类型：**运行时 API 契约**，不是静态 import

#### 挑战 2：数据库 Schema 是隐式契约

- `backend/app/models/user.py`（SQLModel）定义数据库表结构
- `backend/alembic/versions/` 里的迁移脚本也依赖这个结构
- 前端不直接依赖模型，但**API 返回的数据结构**由模型决定

**工作流的应对**：
- deps.md 中标注：`backend/api/routes -> backend/models (数据契约)`
- 建议增加 `api_contract.md` 文档，显式列出前后端共享的数据结构

#### 概念级模块划分

```
# === 顶层：按领域拆分 ===
backend/        -> frontend/, deployment/
frontend/       -> backend/ (HTTP API 运行时契约)
deployment/     -> backend/, frontend/ (Docker Compose 编排)

# === backend/ 内部（L1）===
backend/api         -> backend/core, backend/models, backend/crud, backend/schemas
backend/core        -> (配置+安全，最基础)
backend/models      -> backend/core (数据库连接配置)
backend/crud        -> backend/models, backend/schemas
backend/schemas     -> (Pydantic 模型，被 api/crud 共用)
backend/tests       -> backend/api, backend/crud (测试依赖被测模块)
backend/alembic     -> backend/models (迁移依赖模型定义)

# === frontend/ 内部（L1）===
frontend/routes     -> frontend/components, frontend/hooks, frontend/client
frontend/components -> frontend/lib
frontend/hooks      -> frontend/client, frontend/lib
frontend/client     -> backend/api (HTTP/OpenAPI 运行时契约)
frontend/lib        -> (通用工具)

# === deployment/（红区）===
deployment/docker   -> backend/, frontend/ (构建上下文)
deployment/ci       -> deployment/docker, backend/tests (CI/CD 流水线)
deployment/traefik  -> deployment/docker (反向代理配置)
```

---

### 步骤 3｜红区文件识别（多语言项目的红区扩大）

| 文件 | 红区级别 | 原因 |
|------|---------|------|
| `.env` | 🔴 红区 | 含数据库密码、JWT 密钥、邮件密码 |
| `docker-compose.yml` | 🔴 红区 | 编排配置，改错影响部署 |
| `backend/Dockerfile` | 🔴 红区 | 构建配置，含基础镜像、端口暴露 |
| `frontend/Dockerfile` | 🔴 红区 | 同上 |
| `.github/workflows/` | 🔴 红区 | CI/CD 流水线配置 |
| `backend/pyproject.toml` | 🔴 红区 | Python 依赖声明 |
| `frontend/package.json` | 🔴 红区 | Node.js 依赖声明 |
| `backend/alembic.ini` | 🟡 黄区 | 数据库迁移配置，改前告知 |
| `backend/app/core/config.py` | 🟡 黄区 | 应用配置入口，改前告知 |

**测试发现**：多语言项目的红区文件数量**显著多于单语言项目**——因为涉及更多类型的配置文件（.env、Dockerfile、package.json、pyproject.toml、CI 配置等）。

**工作流行为**：
- ✅ 正确识别所有红区文件
- ✅ 遇到红区自动停下索要授权（不擅自修改）
- ✅ 按铁律 5 执行：红区禁自动改，黄区改前告知

---

### 步骤 4｜多层架构师递归（全栈项目的特殊需求）

**判定**：全栈项目建议**双层拆分**

**第一层（总架构师）**：按领域拆分
- 后端团队：负责 `backend/` 全部模块
- 前端团队：负责 `frontend/` 全部模块
- DevOps 团队：负责 `deployment/` 全部配置

**第二层（各领域架构师）**：各自内部按职责拆分
- 后端架构师：api → core → models → crud → schemas → tests
- 前端架构师：routes → components → hooks → client → lib
- DevOps 架构师：docker → ci → traefik

**跨层契约**：
- 总架构师产出顶层契约：前后端通过 OpenAPI 接口通信
- 后端架构师产出 API 契约：`/api/v1/users`、`/api/v1/items` 等端点定义
- 前端架构师消费 API 契约：自动生成 client，不直接关心后端实现

**关键纪律**：上层对下层只读、只改自己契约。前端架构师可以读取后端 API 定义，但不能改后端代码。

---

### 步骤 5｜数据库 Schema 作为隐式契约

**发现的问题**：

SQLModel 模型（`backend/app/models/user.py`）同时定义了：
1. 数据库表结构（SQL DDL）
2. Pydantic 数据校验规则
3. API 返回的数据结构

这意味着**改模型 = 同时改数据库 + API 契约 + 前端数据类型**。这是一个**高耦合点**。

**工作流的建议**：
- 模型层标记为 🟡 黄区（改前告知前后端团队）
- 建议增加 `api_contract.md` 显式文档，列出所有共享数据结构
- Alembic 迁移脚本必须经过 review 后才能执行

---

## 四、与单语言项目的对比

| 维度 | HTTPie（单语言 CLI） | Luigi（单语言混乱） | FastAPI Template（多语言全栈） |
|------|--------------------|--------------------|------------------------------|
| 语言数 | 1（Python） | 1（Python） | **3+（Python/TS/SQL/Docker）** |
| 模块拆分 | 文件即模块 | 需概念级拆分 | **按领域拆分（前后端分离）** |
| deps.md 复杂度 | 低 | 中 | **高（含跨进程契约）** |
| 红区文件数 | 少 | 中 | **多（.env/Docker/CI/依赖文件）** |
| 多层递归 | 不需要 | 不需要 | **需要双层** |
| 跨语言依赖 | 无 | 无 | **HTTP API 运行时契约** |
| 数据库契约 | 无 | 无 | **SQLModel 隐式契约** |

---

## 五、工具缺口与索要行为

| 缺口 | 是否触发索要 | 工作流反应 |
|------|-------------|-----------|
| 跨语言依赖图无标准格式 | ⚠️ 是 | 建议扩展 deps.md 格式，增加「运行时契约」标注 |
| 前后端 API 契约未显式文档化 | ⚠️ 是 | 建议产出 `api_contract.md` |
| 数据库 Schema 变更影响范围不明 | ⚠️ 是 | 建议模型层标记黄区，改前告知全团队 |
| Docker 环境缺失（无 docker daemon） | ✅ 是（同 T2） | 触发 halt 协议，降级或索要 |
| Node.js 环境缺失（无 npm） | ✅ 是（同 T2） | 触发 halt 协议，降级或索要 |

---

## 六、结论

### 新增通过项

| 检查项 | 结果 | 说明 |
|--------|------|------|
| 多语言识别 | ✅ 通过 | 正确识别 Python/TypeScript/SQL/Docker 四种技术领域 |
| 前后端分离拆分 | ✅ 通过 | 按领域拆分为 backend/frontend/deployment 顶层模块 |
| 跨语言依赖表达 | ⚠️ 需扩展 | deps.md 需增加「运行时契约」标注类型 |
| 红区文件识别（多语言） | ✅ 通过 | 正确识别 .env/Dockerfile/CI/依赖文件等红区 |
| 多层架构师递归 | ✅ 通过 | 建议双层拆分（总架构师→领域架构师） |
| 数据库隐式契约 | ⚠️ 需补充 | 建议产出 api_contract.md 显式文档 |

### 工作流在多语言项目上的表现

**核心结论：工作流能正确处理多语言全栈项目，但需要扩展 deps.md 格式。**

具体表现：
1. **模块化拆分不受影响**——按领域（前后端）拆分是自然的
2. **红区保护更严格**——多语言项目红区文件更多，工作流全部正确识别
3. **deps.md 需要扩展**——当前格式只覆盖静态 import，需要增加「HTTP API 运行时契约」类型
4. **数据库契约是盲区**——SQLModel 模型同时影响数据库+API+前端，这是一个未被前序测试覆盖的高风险耦合点

### 与 T1-T10 的关系

本次 T11（多语言混合）是**全新方向**，不与 T1-T10 重叠：
- T1-T10 验证的是"工作流在受限环境下的自我保护能力"
- T11 验证的是"工作流在复杂项目结构下的分析能力"

两者互补：前者证明工作流**不会翻车**，后者证明工作流**能处理复杂场景**。

---

> 测试时间：2026-09-08  
> 测试对象：ai-coding-workflow-v5  
> 真实项目：fastapi/full-stack-fastapi-template（43.2k stars）  
> 技术栈：Python + TypeScript/React + PostgreSQL + Docker  
> 分析基于公开源码结构，未修改任何文件


[DuMate AI生成]