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

## RK 工具链（tools/ · v2.7 补录）

> 此前遗漏：这批脚本已在实际项目中使用并上传仓库，但未进账本，
> 导致账本记 34 项、仓库实际 42 项。已核对补齐。
> 设计原则见 `docs/RK工具链-AI判断与代码执行.md`：**确定性高的交代码，判断交给 AI**。

| # | 路径 | 行数 | 字节 | md5 |
|---|---|---:|---:|---|
| 35 | `tools/rk_core.py` | 135 | 4336 | `710998399c463ffc3c064e040c54cdf9` |
| 36 | `tools/rk_baseline.py` | 176 | 6755 | `7ebf1b0fe62cfdab91918f0542ffd268` |
| 37 | `tools/rk_morph.py` | 106 | 4033 | `63c15cbd3508fbf911d98d4fe7af5ac7` |
| 38 | `tools/rk_probe.py` | 135 | 5148 | `5b451e6d56fab9e9d7b9ceaae1592ebd` |
| 39 | `tools/rk_extract.py` | 153 | 5636 | `1bd23d81dfab7d276def14cfa3bcee02` |
| 40 | `tools/rk_cve.py` | 142 | 5566 | `8ad882c50a5cc1dc37b7b795c3bf7952` |
| 41 | `tools/rk_report.py` | 127 | 4813 | `15d130e4648580e3661cacdbfe561c24` |
| 42 | `tools/anonymize.py` | 126 | 5233 | `6baa463989f5c6554fdf3d04defef558` |

**安全内核（不可绕过）**：
`rk_core.py:17` 的 `SAFE_METHODS = {"GET","HEAD","OPTIONS"}`，传 POST/PUT/DELETE 直接
`raise UnsafeMethod`；`rk_probe.py` 的 `--allow-host` 白名单硬拦截非授权资产。
这两条是硬编码，AI 无法绕过——**只读铁律由代码保证，不靠自觉**。

**注**：`tools/anonymize.py` 为脱敏公开版（示例域名 `example.edu.cn`、厂商 `VENDOR-A/B/C`）。
本地私用版含真实映射，不上传。

## smoke_test 覆盖缺口（待办）

当前 `scripts/smoke_test.py` 41 条命令**不覆盖** `tools/` 下 8 个脚本。
补测项：rk_morph 形态展开、rk_probe 层标签、rk_cve 边界值判定、rk_core 方法拦截。

## 版本演进

| 版本 | 新增 |
|---|---|
| v2.6 | P14 成熟架构指纹匹配 + 低频验证、P-1 四语言表 |
| v2.6.1 | 修复 gate 静默失败、新增 smoke_test.py |
| v2.6.2 | 架构池补教育行业、P14 端点语义纪律（CAS 案例） |
| v2.7 | **P3 拆分**（P3a 未授权匿名可验 / P3b 越权需 A/B）、写类洞能力边界声明、MANIFEST 补录 tools 8 项 |
