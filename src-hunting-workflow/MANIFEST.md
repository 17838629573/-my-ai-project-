# 交付产物账本 · SRC 挖洞工作流

> 账本，不是产物。版本 v2.3（版本升级敞口 · 开工第一问）。

---

## 权威清单

| # | 路径 | 行数 | 字节 | md5 |
|---|---|---:|---:|---|
| 1 | `AGENT_BOOTSTRAP.md` | 287 | 10341 | `8c82b81349266ce3b6db10b981d80898` |
| 2 | `README.md` | 236 | 7641 | `10c266a2007a9a42d29ab5cbb689861f` |
| 3 | `WORKFLOW.md` | 450 | 18348 | `6b67fbdb09e9e3ce7df6318e163a3cb1` |
| 4 | `dist/src-hunting-workflow-v2.3.zip` | 1531 | 203479 | `b2e1bb0510a4c37ffa5295bd4e9fbad9` |
| 5 | `docs/SRC厂商改动对齐法.md` | 213 | 8617 | `c94841d36031c534140059bf895ee591` |
| 6 | `docs/前沿漏洞拆解与外推分析.md` | 319 | 50234 | `a340f8643790a5d07c9ab005cd8b32ea` |
| 7 | `docs/实网静态分析-能力边界与诚实结论.md` | 138 | 5653 | `b425a1d530f338c23b1fd74aedc85446` |
| 8 | `docs/工作流升级-v2.1-根因族层.md` | 169 | 5965 | `e34bbac0f61cc77ff880e6b6f12e3807` |
| 9 | `docs/工作流升级-v2.2-底层根因映射层.md` | 177 | 7384 | `49ebb93c34753644f54a39e2d9bd163e` |
| 10 | `docs/工作流升级-v2.3-版本升级敞口.md` | 189 | 7257 | `95eaa1f54020fa5b2ad4e4fdbaf77096` |
| 11 | `docs/工作流实网走查-五个公开目标.md` | 224 | 11189 | `91677052d89815172c611b7a856882cd` |
| 12 | `docs/案例模式映射.csv` | 11 | 925 | `046729fa7170a00fd9d151f95a01ff53` |
| 13 | `docs/源码静态分析-Nextcloud静默补丁实证.md` | 184 | 6861 | `da55172b32d1a6ed9207b902d300800d` |
| 14 | `docs/规则库挖掘-CWE347根因族谱.md` | 231 | 8502 | `da13dd574a56a826b24d59771f3ce72a` |
| 15 | `docs/闭源公告反推十例.md` | 610 | 49365 | `0924054006f61f72e774f2e971e6730c` |
| 16 | `scripts/intel_profile.json` | 61 | 866 | `f9b0b49e49246784470cede8e3292f9d` |
| 17 | `scripts/mock_patchdiff.py` | 149 | 5920 | `c058c9fef0855c8397bb53ea9a1dc032` |
| 18 | `scripts/mock_target.py` | 59 | 2501 | `44d78b94ed8dcf1923a4203616353a5f` |
| 19 | `scripts/run.py` | 261 | 10491 | `0ca7b4c73f3bc47e75a3595e3e39fdf1` |
| 20 | `scripts/src_calibrate.py` | 360 | 15634 | `24158157b65e2b053fe3f4ad85a14b6b` |
| 21 | `scripts/src_gitpatch.py` | 304 | 11989 | `c1ed43681751b4cfe61ce77ee65955aa` |
| 22 | `scripts/src_intel.py` | 332 | 13537 | `c900d85c124c288b50595588d2c95c22` |
| 23 | `scripts/src_patchdiff.py` | 335 | 14381 | `bfe96941b686e3e4ed1d5325cebe0f88` |
| 24 | `scripts/src_rules.py` | 393 | 14363 | `d3cd4c5dec143e5cbc36cc562a747c49` |
| 25 | `scripts/src_scout.py` | 437 | 16540 | `f6cbe77c530cda8f5645b431cf2fee7f` |
| 26 | `scripts/src_stack.py` | 525 | 28149 | `ab64dcf2f4ea8b4e2afbc6879eb0e8ff` |
| 27 | `scripts/src_variant.py` | 511 | 23274 | `b0b7726488a7322c8aa8de2ada4616ef` |

## 分层说明

- `WORKFLOW.md` —— 主干，常驻上下文。开工第一问 + 十四步 + 三条铁律 + 提交纪律
- `README.md` —— 门面，设计原理与快速开始
- `AGENT_BOOTSTRAP.md` —— 给外部 Agent 的自举说明：先测能力再选路径
- `scripts/` —— 8 个脚本 + 2 个本地靶场 + 技术栈配置
- `docs/` —— 实证报告与方法论文档（按需加载，不常驻）
- `dist/` —— 完整打包（含参考库）

## 加载纪律

任意时刻上下文 = WORKFLOW.md（常驻）+ 当前步骤的引导提问。
P10–P13 是专家模块，按需调取，不要一次全读。
docs/ 下的报告按需调取，不要一次全读。

## 版本演进

| 版本 | 新增 |
|---|---|
| v2.1 | P9 根因族层、src_rules.py、21 维泛化 |
| v2.2 | P10-P13 底层根因映射层、src_stack.py、24 维泛化 |
| v2.3 | P-1 版本升级敞口（开工第一问）、26 维泛化 |
