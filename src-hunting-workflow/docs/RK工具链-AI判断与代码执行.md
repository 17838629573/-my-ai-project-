# RK 工具链：AI 做判断，代码做执行

## 为什么要有这一层

之前把工作流拆成 15 步、每步 3 条规则，是为了让执行方"记得住"。但拆细之后出现新问题：

**AI 开始一步步手工执行本该由代码批量完成的事** —— 手搓 URL 列表、肉眼看长度比对、凭记忆判 CVE 版本范围。结果是慢、易漏、且会拿"请求少"当模糊答案的借口。

正确分工：

| 确定性高、可批量 | 交给代码 |
|---|---|
| 需要语义判断、需要联网认知 | 交给 AI |

**判断标准一句话**：能用 `if/else` 表达的，写进脚本；需要"这看起来像什么"的，留给 AI。

---

## 工具一览（7 个，单文件、零依赖可选）

| 脚本 | 干什么（确定性部分） | AI 还剩什么活 |
|---|---|---|
| `rk_core.py` | **内核**：非 GET/HEAD/OPTIONS 一律抛错拒绝；响应指纹；基线比对；证据落盘 `.h/.b/.json` | 无——它是被其他脚本调用的 |
| `rk_baseline.py` | 5–8 个请求自动建**响应层基线**并聚类命名（`404_N`/`auth_wall`/`200_empty`/`30x`/`400_badreq`…），顺带扫版本串 | 决定"这个目标的层是什么意思" |
| `rk_morph.py` | **形态变体自动生成**：目录/首页/后缀互换/`.show.jsp` 数据面/编码变体，一条路径扩成 10–20 条 URL | 不需要手搓 URL 了 |
| `rk_probe.py` | 批量只读探测，自动对照基线**打层标签**，自动标 `NEW`（异常/新层），0B 与 30x 单独标记 | 只看 `NEW` 那几行 |
| `rk_extract.py` | 从源码/存档提取路径：**自动判编码**（GBK 坑）、抠 `href/action/onclick/_webRootPath` 拼接、抠参数名与表单字段 | 挑哪条值得打 |
| `rk_cve.py` | 版本 × CVE 范围**确定性比对**，含里程碑版本排序与边界值判定、EOL 无补丁提示 | **联网查 CVE 并填 feed** |
| `rk_report.py` | 渲三态清单，**自动拦截措辞红线** | 填 findings，看红线告警 |

---

## 典型流水线（AI 只做 4 个判断）

```bash
# 1 建基线（代码自动探测+聚类+扫版本）
python3 rk_baseline.py https://target --auth /system/ --out base.json

# 2 提取目标自述路径（代码读源码，AI 零手搓）
python3 rk_extract.py -d evidence/ --urls-only > urls.txt

# 3 生成形态变体（代码扩 URL）
python3 rk_morph.py -f urls.txt --base https://target --out cand.txt

# 4 批量探测（代码打层标签，AI 只看 NEW）
python3 rk_probe.py -f cand.txt --baseline base.json --ev ev/

# 5 AI 联网查 CVE → 填 feed.json
python3 rk_cve.py --init tomcat            # 拿模板
python3 rk_cve.py --version <版本串·示例> --feed feed.json

# 6 报告（代码查措辞红线）
python3 rk_report.py -f findings.json -o report.md
```

**AI 全程只做四件事**：① 选目标/定资产优先级 ② 联网查 CVE 填 feed ③ 看 `NEW` 行做语义判断 ④ 填 findings 决定三态与定级。

---

## 已验证（本地 mock 目标跑通）

| 能力 | 验证结果 |
|---|---|
| 形态分流自动发现 | ✅ `/examples/` 目录→网关层 vs `/examples/index.jsp`→应用层，代码自动标 `NEW` |
| jwmis 式后缀分流 | ✅ `.jsp` 放行 / `.html` 被 filter 拦，22 条变体一次跑完，11 条 `NEW` 全部列出 |
| GBK 编码坑 | ✅ GBK 存档自动转码，`_webRootPath+"public/<自述路径·校历>"` 正确抠出 |
| CVE 边界值 | ✅ <版本串·示例> 命中 4 条（含"需升级至 9.0.109"）；9.0.109 复核后 55752/55754 正确转为未命中 |
| EOL 分支提示 | ✅ 无修复版本时输出"EOL 分支：上游不再提供补丁" |
| 措辞红线 | ✅ "已确认无鉴权"→告警改"未观察到鉴权拦截"；"可执行代码"→告警 |
| 硬纪律 | ✅ `rk_core` 对 POST/PUT/DELETE 直接抛 `UnsafeMethod` |

---

## 与 15 步手册的关系

- **15 步手册** = 想什么（心智模型，防漏项）
- **RK 工具链** = 干什么（执行，防手误、防重复劳动）

不要二选一。手册里 S5 基线、S6 0B、S7 形态、S11 CVE 对应本工具链的 `rk_baseline` / `rk_probe` / `rk_morph` / `rk_cve`。

---

## 硬纪律（写进代码，不靠自觉）

1. **只允许 GET/HEAD/OPTIONS** —— `rk_core.SAFE_METHODS` 在请求出口硬拦，非安全方法抛异常
2. **域名白名单** —— `--allow-host`，越界直接拒
3. **证据全落盘** —— 每次响应写 `.h`（头）+ `.b`（体）+ `.json`（指纹），可回溯
4. **不做写入** —— 探测层面不提供 POST/PUT 能力

---

## 已知限制

- **CVE 数据不能自动拉取**：沙盒出口策略拦截 NVD/OSV（403）。因此 feed 由 AI 用 `web_search` 获取后录入，`rk_cve.py` 只做确定性比对——**这恰恰是分工的正确形态**：联网认知归 AI，版本比对归代码。
- `rk_extract` 对 `_webRootPath` 拼接目前输出相对路径，需自行补前缀（后续可加自动拼接）。
