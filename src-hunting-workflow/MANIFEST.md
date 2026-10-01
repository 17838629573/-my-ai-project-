# 交付产物账本 · SRC 挖洞工作流

> 账本。版本 v2.6.2（教育行业架构池 + 端点语义纪律）。

> **上传前必做：`python3 scripts/smoke_test.py` 必须全绿**（10 脚本 × 41 命令）。

---

## 权威清单

| # | 路径 | 行数 | 字节 | md5 |
|---|---|---:|---:|---|
| 1 | `AGENT_BOOTSTRAP.md` | 371 | 13774 | `<MD5>` |
| 2 | `README.md` | 267 | 9008 | `<MD5>` |
| 3 | `WORKFLOW.md` | 524 | 22019 | `<MD5>` |
| 4 | `docs/P14实战-<厂商C·统一认证>authserver架构深挖.md` | 195 | 8374 | `<MD5>` |
| 5 | `docs/SRC厂商改动对齐法.md` | 213 | 8617 | `<MD5>` |
| 6 | `docs/前沿漏洞拆解与外推分析.md` | 319 | 50234 | `<MD5>` |
| 7 | `docs/实网静态分析-能力边界与诚实结论.md` | 138 | 5653 | `<MD5>` |
| 8 | `docs/工作流修订-v2.4-实跑反馈落地.md` | 144 | 5697 | `<MD5>` |
| 9 | `docs/工作流修订-v2.5.1-重跑验证修复.md` | 120 | 3479 | `<MD5>` |
| 10 | `docs/工作流修订-v2.6.1-gate静默失败修复.md` | 109 | 3601 | `<MD5>` |
| 11 | `docs/工作流升级-v2.1-根因族层.md` | 169 | 5965 | `<MD5>` |
| 12 | `docs/工作流升级-v2.2-底层根因映射层.md` | 177 | 7384 | `<MD5>` |
| 13 | `docs/工作流升级-v2.3-版本升级敞口.md` | 189 | 7257 | `<MD5>` |
| 14 | `docs/工作流升级-v2.5-确定性规则硬化.md` | 179 | 5869 | `<MD5>` |
| 15 | `docs/工作流升级-v2.6-架构匹配与语言升级敞口.md` | 126 | 5210 | `<MD5>` |
| 16 | `docs/工作流实网走查-五个公开目标.md` | 224 | 11189 | `<MD5>` |
| 17 | `docs/案例模式映射.csv` | 11 | 925 | `<MD5>` |
| 18 | `docs/源码静态分析-Nextcloud静默补丁实证.md` | 184 | 6861 | `<MD5>` |
| 19 | `docs/规则库挖掘-CWE347根因族谱.md` | 231 | 8502 | `<MD5>` |
| 20 | `docs/闭源公告反推十例.md` | 610 | 49365 | `<MD5>` |
| 21 | `scripts/intel_profile.json` | 61 | 866 | `<MD5>` |
| 22 | `scripts/mock_patchdiff.py` | 149 | 5920 | `<MD5>` |
| 23 | `scripts/mock_target.py` | 59 | 2501 | `<MD5>` |
| 24 | `scripts/run.py` | 261 | 10491 | `<MD5>` |
| 25 | `scripts/smoke_test.py` | 171 | 5688 | `<MD5>` |
| 26 | `scripts/src_calibrate.py` | 483 | 21774 | `<MD5>` |
| 27 | `scripts/src_gate.py` | 366 | 14704 | `<MD5>` |
| 28 | `scripts/src_gitpatch.py` | 304 | 11989 | `<MD5>` |
| 29 | `scripts/src_intel.py` | 332 | 13537 | `<MD5>` |
| 30 | `scripts/src_patchdiff.py` | 335 | 14381 | `<MD5>` |
| 31 | `scripts/src_rules.py` | 418 | 15286 | `<MD5>` |
| 32 | `scripts/src_scout.py` | 437 | 16540 | `<MD5>` |
| 33 | `scripts/src_stack.py` | 713 | 37620 | `<MD5>` |
| 34 | `scripts/src_variant.py` | 511 | 23274 | `<MD5>` |

## 版本演进

| 版本 | 新增 |
|---|---|
| v2.6 | P14 成熟架构指纹匹配 + 低频验证、P-1 四语言表 |
| v2.6.1 | 修复 gate 静默失败、新增 smoke_test.py |
| v2.6.2 | 架构池补教育行业、P14 端点语义纪律（CAS 案例） |
