# 交付产物账本

> 账本，不是产物。生成日期：2026-09-10。

---

## 权威清单：20 份产物（+ 本账本共 21 份文件）

| # | 路径 | 行数 | 字节 | md5 | 角色 |
|---|---|---:|---:|---|---|
| 1 | `.gitignore` | 6 | 56 | `ce5edf4bc92631a4fceb0d1ce1f08778` | 标配 |
| 2 | `LICENSE` | 23 | 1164 | `30298cb6fbe9e6aad2724bde2eebb2ca` | 标配 |
| 3 | `README.md` | 69 | 4811 | `105065e4ac5a1eddc92e5ae2537adaca` | 门面 |
| 4 | `WORKFLOW.md` | 61 | 6247 | `00a9e5571c32465df621957800373490` | 主干(常驻) |
| 5 | `ERRORS.md` | 32 | 1438 | `64a77340cf0e1fb5e7f49508f72cfed4` | 失败库(常驻记忆层) |
| 6 | `skills/apk/SKILL.md` | 13 | 523 | `debc3dc38abe99bee852e53bd453f6a9` | 步骤7·打APK |
| 7 | `skills/architect/SKILL.md` | 21 | 1224 | `ae2738410a13d92b3ec9c6a423ed47bd` | 通用·架构师层级 |
| 8 | `skills/check/SKILL.md` | 28 | 1673 | `be185173f8040f8ac0f27c75f69e992f` | 通用·静态检查 |
| 9 | `skills/fix/SKILL.md` | 22 | 1368 | `2f0afee403547485460e5dcacf372754` | 通用·精准修改 |
| 10 | `skills/halt/SKILL.md` | 34 | 2262 | `a978f8722b8808c45cacdea3cb1ccfe8` | 通用·卡住协议 |
| 11 | `skills/install/SKILL.md` | 18 | 1070 | `4b4eb6b2bdd3d37a84d119a00bb6cc72` | 安装工作流 |
| 12 | `skills/split/SKILL.md` | 24 | 2607 | `e2607b08bb99da32f1ffd970f6f63109` | 步骤2·拆模块(架构师层级) |
| 13 | `skills/test/SKILL.md` | 22 | 1160 | `ae8b1467fc8b279c0f5378406b7c79ec` | 步骤5·测试找bug |
| 14 | `skills/track/SKILL.md` | 32 | 1712 | `bdbfa3da912f8df05c906fade9cd0f46` | 通用·授权跟踪 |
| 15 | `skills/verify/SKILL.md` | 26 | 1047 | `f19fddd2565569a21cd8e0ee8fbd9469` | 通用·验证 |
| 16 | `skills/write/SKILL.md` | 19 | 1455 | `61f0690bb3e48472689d04d39e8bbd7e` | 步骤3·写模块 |
| 17 | `scripts/dep_check.py` | 193 | 8198 | `4ee4c871e2dd25408eb3be34ec4d64b0` | 脚本·依赖图验证 |
| 18 | `scripts/enforce.py` | 436 | 15087 | `c80d07bfc88a8546b3e60792c0c9a448` | **脚本·执行门禁** |
| 19 | `scripts/install.sh` | 39 | 1983 | `02fb9704900aeb2630c3913e829f8475` | 脚本·一键安装 |

**加载规则**：常驻 `WORKFLOW.md`（铁律 9 条 + 执行门禁 + 断点续作 + 入口判断 + 7 步主干）；`ERRORS.md` 为常驻记忆层，halt 触发时写入、用户定期 review，不计入每步上下文。步骤文件由主干点名加载；通用模块（track/architect/verify/fix/check/halt）由步骤在需要时点名调用，用完回主干。任意时刻上下文 = WORKFLOW + 当前步骤文件 + 至多一个通用模块。

**运行时产物（不入账本、不入库）**：`.track.md` 授权跟踪文件（`.gitignore` 已排除，跟人走）；`deps.md` 全局契约图（步骤 2 产出，层间 `# L0`/`# L1` 标注，步骤 4 校验）；`WORKLOG.md`（每步过门强制追加一行，断点续作用，由 `enforce.py gate post-step` 校验）。

**脚本验证**：
- `dep_check.py`：已用构造项目 + 真实案例实测——正常图仅报孤立模块 warning（退出码 0）；循环依赖、未声明依赖均准确报 error（退出码 1）。2026-09-08 真实 clairvoyance 项目实测修复 3 个解析缺陷；2026-09-09 多语言样例实测括号注释、`[runtime]`、ESM import 均正确。
- `enforce.py`：2026-09-10 实测 6 项子命令全通：validate 自检通过、check-write 红区无授权阻断/有授权放行、check-auth 无track阻断/有track放行、check-iron-law 铁律被删阻断/完整放行、gate post-step 无WORKLOG阻断/有记录放行、check-evidence 正确核验退出码。
- `install.sh`：已实测 CodeBuddy / Trae / Claude / Cursor / Copilot / 无工具 六个分支落位正确。
