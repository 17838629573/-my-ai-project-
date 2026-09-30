# 交付产物账本 · SRC 挖洞工作流

> 账本。版本 v2.6.2（教育行业架构池 + 端点语义纪律）。

> **上传前必做：`python3 scripts/smoke_test.py` 必须全绿**（10 脚本 × 41 命令）。

---

## 权威清单

| # | 路径 | 行数 | 字节 | md5 |
|---|---|---:|---:|---|
| 1 | `AGENT_BOOTSTRAP.md` | 371 | 13774 | `6543393d67947f0b6d8db7f45efc0b51` |
| 2 | `README.md` | 267 | 9008 | `49ba26b0c62790745f1d58ed21607e8d` |
| 3 | `WORKFLOW.md` | 524 | 22019 | `155441382bab929c5b305a0a74dc3572` |
| 4 | `docs/P14实战-金智authserver架构深挖.md` | 195 | 8374 | `b100a3b43246e4d8fa576e36de562ad3` |
| 5 | `docs/SRC厂商改动对齐法.md` | 213 | 8617 | `c94841d36031c534140059bf895ee591` |
| 6 | `docs/前沿漏洞拆解与外推分析.md` | 319 | 50234 | `a340f8643790a5d07c9ab005cd8b32ea` |
| 7 | `docs/实网静态分析-能力边界与诚实结论.md` | 138 | 5653 | `b425a1d530f338c23b1fd74aedc85446` |
| 8 | `docs/工作流修订-v2.4-实跑反馈落地.md` | 144 | 5697 | `c4ef34e193a33dd4a00f64ed84f63e64` |
| 9 | `docs/工作流修订-v2.5.1-重跑验证修复.md` | 120 | 3479 | `53a82a57314b00a40797d3e5edf431cc` |
| 10 | `docs/工作流修订-v2.6.1-gate静默失败修复.md` | 109 | 3601 | `570b02269fe5ba8f1b2317829f7bb1a2` |
| 11 | `docs/工作流升级-v2.1-根因族层.md` | 169 | 5965 | `e34bbac0f61cc77ff880e6b6f12e3807` |
| 12 | `docs/工作流升级-v2.2-底层根因映射层.md` | 177 | 7384 | `49ebb93c34753644f54a39e2d9bd163e` |
| 13 | `docs/工作流升级-v2.3-版本升级敞口.md` | 189 | 7257 | `95eaa1f54020fa5b2ad4e4fdbaf77096` |
| 14 | `docs/工作流升级-v2.5-确定性规则硬化.md` | 179 | 5869 | `c5b7bc1d2c2216dccb0f75a7ad6e6f85` |
| 15 | `docs/工作流升级-v2.6-架构匹配与语言升级敞口.md` | 126 | 5210 | `a656f9fc5d30e5ecb34b31a9fdfd2f7c` |
| 16 | `docs/工作流实网走查-五个公开目标.md` | 224 | 11189 | `91677052d89815172c611b7a856882cd` |
| 17 | `docs/案例模式映射.csv` | 11 | 925 | `046729fa7170a00fd9d151f95a01ff53` |
| 18 | `docs/源码静态分析-Nextcloud静默补丁实证.md` | 184 | 6861 | `da55172b32d1a6ed9207b902d300800d` |
| 19 | `docs/规则库挖掘-CWE347根因族谱.md` | 231 | 8502 | `da13dd574a56a826b24d59771f3ce72a` |
| 20 | `docs/闭源公告反推十例.md` | 610 | 49365 | `0924054006f61f72e774f2e971e6730c` |
| 21 | `scripts/intel_profile.json` | 61 | 866 | `f9b0b49e49246784470cede8e3292f9d` |
| 22 | `scripts/mock_patchdiff.py` | 149 | 5920 | `c058c9fef0855c8397bb53ea9a1dc032` |
| 23 | `scripts/mock_target.py` | 59 | 2501 | `44d78b94ed8dcf1923a4203616353a5f` |
| 24 | `scripts/run.py` | 261 | 10491 | `0ca7b4c73f3bc47e75a3595e3e39fdf1` |
| 25 | `scripts/smoke_test.py` | 171 | 5688 | `152c94b51a88169ed2c60aa88ac6354a` |
| 26 | `scripts/src_calibrate.py` | 483 | 21774 | `6775ceb4fbb2a9093177600859695520` |
| 27 | `scripts/src_gate.py` | 366 | 14704 | `2559de46fde300377d8e8aafcd168473` |
| 28 | `scripts/src_gitpatch.py` | 304 | 11989 | `c1ed43681751b4cfe61ce77ee65955aa` |
| 29 | `scripts/src_intel.py` | 332 | 13537 | `c900d85c124c288b50595588d2c95c22` |
| 30 | `scripts/src_patchdiff.py` | 335 | 14381 | `bfe96941b686e3e4ed1d5325cebe0f88` |
| 31 | `scripts/src_rules.py` | 418 | 15286 | `4207285f7c84952f6572ed7e73813bb5` |
| 32 | `scripts/src_scout.py` | 437 | 16540 | `f6cbe77c530cda8f5645b431cf2fee7f` |
| 33 | `scripts/src_stack.py` | 713 | 37620 | `809423e87957584530569beaf3c5f1a6` |
| 34 | `scripts/src_variant.py` | 511 | 23274 | `b0b7726488a7322c8aa8de2ada4616ef` |

## 版本演进

| 版本 | 新增 |
|---|---|
| v2.6 | P14 成熟架构指纹匹配 + 低频验证、P-1 四语言表 |
| v2.6.1 | 修复 gate 静默失败、新增 smoke_test.py |
| v2.6.2 | 架构池补教育行业、P14 端点语义纪律（CAS 案例） |
