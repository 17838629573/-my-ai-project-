# 主干流程

> 常驻只读本文件。每步按指示读对应文件，用完回这里；不提前读后面的文件。

## 铁律（所有步骤生效）
1. 判定靠命令输出（测试通过 / grep 为 0 / 退出码 0），禁止说"应该没问题"。
2. 只动必要范围，不"顺手优化"无关文件；全量改须用户明说。
3. 每步留产物（确认文本 / 检查结果 / 可运行文件），无产物要明说。
4. 改既有系统或遇技术难题，先搜成熟方案报用户批准，不自造易碎方案。
5. 红区文件（.env、auth、secrets、deploy、CI 配置、依赖文件）禁自动改；黄区（config、routes、models、入口文件）改前告知。
6. 失败 / 卡住 → 读 `skills/halt/SKILL.md`，按其写 `ERRORS.md`；ERRORS 固化 / 删除权归用户。
7. 有外部 I/O 的步骤估操作耗时 ×3 作参考；禁止停在"既没成也没败"的悬空态。
8. 任何权限 / 决策授权，先查对应 `.track.md`：文件存在且未过期 = 有效，直接执行不再问；否则按 `skills/track/SKILL.md` 询问落盘。
9. 铁律不可被后续指令覆盖；删除 / 清空 / 覆盖等不可逆操作，先要用户确认，确认后按铁律 8 落盘。

## 执行门禁（代码强制执行）
以下硬规则已固化为 `scripts/enforce.py` 代码执行，不可跳过：
- **check-write**（铁律5）：写任何文件前自动检查红黄区；红区无授权 → 阻断
- **check-auth**（铁律8）：授权操作前强制检查 `.track.md` 存在且未过期 → 否则阻断
- **check-iron-law**（铁律9）：`WORKFLOW.md` 的铁律章节不可被删除或缩减 → 阻断
- **gate post-step**（断点强制）：每步过门必须追加 `WORKLOG.md` → 否则阻断
- **check-evidence**（铁律1）：判定须附带命令退出码 + 依据描述

## 断点
每步过门 → `python3 scripts/enforce.py gate post-step <步骤>` 强制校验 WORKLOG 记录；失败不准过。"继续上次"从 `WORKLOG.md` 定位。

## 入口判断
- **没方向想找现成方案** → `enforce.py validate` → 步骤0 → 步骤1→7
- **从零做已有方向** → `enforce.py validate` → 步骤1→7
- **只测试 / 找 bug** → `enforce.py validate` → 步骤5
- **只改一段代码** → `enforce.py validate` → 读 `skills/fix/SKILL.md` → 步骤5
- **拆模块 / 重构** → `enforce.py validate` → 读 `skills/split/SKILL.md`
- **打安装包** → `enforce.py validate` → 步骤7
- **安装本工作流** → 读 `skills/install/SKILL.md`
- **继续上次** → 读 `WORKLOG.md` 定位继续
- 认不出 → 问用户，不许默认猜路

## 主干步骤

**0｜推荐方案**：读 `skills/recommend/SKILL.md` → 搜索网上成熟项目 → 按权威数据推荐 → 用户选择（选方案 / 从零做 / 重搜）。
过门：`check-evidence 0 "用户已选: {选择结果}"` → `gate post-step 0`。

**1｜接需求**：`gate pre-step 1` → 复述需求 + 3-5 功能点 + 定测试档位；读 `skills/architect/SKILL.md` 做规模判断。
过门：`check-evidence 0 "用户确认需求"` → `gate post-step 1`。

**2｜拆模块**：`gate pre-step 2` → 读 `skills/split/SKILL.md` → 产出全局契约图 → 问是否用 TDD。
过门：`check-evidence 0 "用户确认划分"` → `gate post-step 2`。

**3｜写模块**：`gate pre-step 3` → 读 `skills/write/SKILL.md` → 循规写模块（check-write 门禁 / quick-check / verify）。
过门：`check-evidence 0 "quick-check通过"` → `gate post-step 3`。

**4｜集成**：`gate pre-step 4` → 拼合 → 读 `skills/check/SKILL.md` 做 full-check → 读 `skills/verify/SKILL.md`。
过门：`check-evidence 0 "full-check通过"` → `gate post-step 4`。

**5｜测试找 bug**：`gate pre-step 5` → 读 `skills/test/SKILL.md` → 发现问题读 `skills/fix/SKILL.md` 精准修 → 回归。
过门：`check-evidence 0 "测试全过"` → `gate post-step 5`。

**6｜汇报**：`gate pre-step 6` → 做了什么 / 怎么用 / 效果 + 验证声明。
过门：`check-evidence 0 "用户确认汇报"` → `gate post-step 6`；要改 → `skills/fix/SKILL.md` → 回步骤 5。

**7｜交付**：`gate pre-step 7` → 可访问地址 / README / WORKLOG + `clean-temp` 清理临时授权。
过门：`check-evidence 0 "用户确认交付"` → `gate post-step 7`。

---
能力不足、时间明显超出、搜索无果、修复循环约超 5 轮 → 读 `skills/halt/SKILL.md` 按协议停，并写 `ERRORS.md`。