# 交付产物账本 · SRC 挖洞工作流

> 账本，不是产物。版本 v2.5（确定性规则硬化）。

---

## 权威清单

| # | 路径 | 行数 | 字节 | md5 |
|---|---|---:|---:|---|
| 1 | `AGENT_BOOTSTRAP.md` | 371 | 13774 | `6543393d67947f0b6d8db7f45efc0b51` |
| 2 | `README.md` | 262 | 8714 | `41d3e887688212574efc582721793ffa` |
| 3 | `WORKFLOW.md` | 457 | 18230 | `d84d4d4fcdfd9b8f2aaf87396bfd5eda` |
| 4 | `docs/SRC厂商改动对齐法.md` | 213 | 8617 | `c94841d36031c534140059bf895ee591` |
| 5 | `docs/前沿漏洞拆解与外推分析.md` | 319 | 50234 | `a340f8643790a5d07c9ab005cd8b32ea` |
| 6 | `docs/实网静态分析-能力边界与诚实结论.md` | 138 | 5653 | `b425a1d530f338c23b1fd74aedc85446` |
| 7 | `docs/工作流修订-v2.4-实跑反馈落地.md` | 144 | 5697 | `c4ef34e193a33dd4a00f64ed84f63e64` |
| 8 | `docs/工作流升级-v2.1-根因族层.md` | 169 | 5965 | `e34bbac0f61cc77ff880e6b6f12e3807` |
| 9 | `docs/工作流升级-v2.2-底层根因映射层.md` | 177 | 7384 | `49ebb93c34753644f54a39e2d9bd163e` |
| 10 | `docs/工作流升级-v2.3-版本升级敞口.md` | 189 | 7257 | `95eaa1f54020fa5b2ad4e4fdbaf77096` |
| 11 | `docs/工作流升级-v2.5-确定性规则硬化.md` | 179 | 5869 | `c5b7bc1d2c2216dccb0f75a7ad6e6f85` |
| 12 | `docs/工作流实网走查-五个公开目标.md` | 224 | 11189 | `91677052d89815172c611b7a856882cd` |
| 13 | `docs/案例模式映射.csv` | 11 | 925 | `046729fa7170a00fd9d151f95a01ff53` |
| 14 | `docs/源码静态分析-Nextcloud静默补丁实证.md` | 184 | 6861 | `da55172b32d1a6ed9207b902d300800d` |
| 15 | `docs/规则库挖掘-CWE347根因族谱.md` | 231 | 8502 | `da13dd574a56a826b24d59771f3ce72a` |
| 16 | `docs/闭源公告反推十例.md` | 610 | 49365 | `0924054006f61f72e774f2e971e6730c` |
| 17 | `scripts/intel_profile.json` | 61 | 866 | `f9b0b49e49246784470cede8e3292f9d` |
| 18 | `scripts/mock_patchdiff.py` | 149 | 5920 | `c058c9fef0855c8397bb53ea9a1dc032` |
| 19 | `scripts/mock_target.py` | 59 | 2501 | `44d78b94ed8dcf1923a4203616353a5f` |
| 20 | `scripts/run.py` | 261 | 10491 | `0ca7b4c73f3bc47e75a3595e3e39fdf1` |
| 21 | `scripts/src_calibrate.py` | 464 | 20549 | `178987da268cd29c126fff85a32ea6b2` |
| 22 | `scripts/src_gate.py` | 356 | 14205 | `a891751a202c2764976274950a1ff6ca` |
| 23 | `scripts/src_gitpatch.py` | 304 | 11989 | `c1ed43681751b4cfe61ce77ee65955aa` |
| 24 | `scripts/src_intel.py` | 332 | 13537 | `c900d85c124c288b50595588d2c95c22` |
| 25 | `scripts/src_patchdiff.py` | 335 | 14381 | `bfe96941b686e3e4ed1d5325cebe0f88` |
| 26 | `scripts/src_rules.py` | 393 | 14363 | `d3cd4c5dec143e5cbc36cc562a747c49` |
| 27 | `scripts/src_scout.py` | 437 | 16540 | `f6cbe77c530cda8f5645b431cf2fee7f` |
| 28 | `scripts/src_stack.py` | 525 | 28149 | `ab64dcf2f4ea8b4e2afbc6879eb0e8ff` |
| 29 | `scripts/src_variant.py` | 511 | 23274 | `b0b7726488a7322c8aa8de2ada4616ef` |

## 版本演进

| 版本 | 新增 |
|---|---|
| v2.1 | P9 根因族层、src_rules.py、21 维泛化 |
| v2.2 | P10-P13 底层根因映射层、src_stack.py、24 维泛化 |
| v2.3 | P-1 版本升级敞口（开工第一问）、26 维泛化 |
| v2.4 | R1-R4 实跑反馈落地（凭证/零命中/样本/目标选择） |
| v2.5 | src_gate.py 六闸门、主干 557→458 行、提问占比 21%→24% |

## 加载纪律

任意时刻上下文 = WORKFLOW.md（常驻）+ 当前步骤的引导提问。
确定性规则已硬化进 src_gate.py，不要背诵条文，跑脚本即可。
P10–P13 是专家模块，按需调取，不要一次全读。
