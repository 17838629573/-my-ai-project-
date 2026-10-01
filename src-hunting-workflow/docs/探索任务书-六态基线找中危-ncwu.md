# 探索任务书：用「六态响应基线」找中危（ncwu）

> 给执行 AI
> 目标群：www / news / www2（博达 VSB9）· jwmis（青果）· authserver（金智 CAS）
> 核心方法：**先给每个面建立响应基线，再用基线当 oracle 枚举**
> 铁律：**零写入、零登录、零爆破、零注入**
> 目的：找**我们没想到的**中危，不是重复已知结论

---

## 一、最重要的方法：六态响应基线

这个项目对不同类型的请求返回**六种可区分状态**。这不是噪音，是**应用在用响应告诉你内部情况**。

| 状态 | 响应特征 | 泄露的信息 |
|---|---|---|
| ① 网关未放行 | 404 · **1693B** 统一模板 | 该前缀不在网关白名单 |
| ② 应用内不存在 | 404 · **2455B** 博达模板 | **进了应用，但文件不存在** |
| ③ 应用内有锁 | 200 · **912B** 登录提示页 | 该路径被登录前置接管 |
| ④ 免鉴权有内容 | 200 + 实际内容 | 文件存在且可读 |
| ⑤ 免鉴权但空 | 200 · **0B** | 受理但无回执（可能掩盖写入） |
| ⑥ 容器/框架异常 | 400/500 · 2304B 栈 | 泄露技术栈与版本 |

**用法**：②和④的差别 = **文件存在性判别器**；③和④的差别 = **鉴权边界判别器**。

**这个 oracle 的价值**：通用字典是"猜有没有这个文件"（前四轮 215 请求全废），而它是"应用直接回答在不在"。

---

## 二、第一步（必做）：给每个面建立自己的基线

**不要假设各面基线相同。** 对每个新目标先用 3 个请求取基线：

```
1. GET /<随机串>.html                 → 取网关基线（应该是 1693B 或同类）
2. GET /system/<随机串>.jsp           → 取鉴权基线（912B？）
3. GET /system/resource/<随机串>.js   → 取应用内不存在基线（2455B？）
```

**要测的面**（按优先级）：

| 面 | 域名 | 已知 |
|---|---|---|
| 主站 | www.ncwu.edu.cn | 基线已建立（1693/2455/912） |
| **news** | news.ncwu.edu.cn | **基线未建立** ★ |
| **www2** | www2.ncwu.edu.cn | **基线未建立** ★ |
| **jwmis** | jwmis.ncwu.edu.cn | 已知：未认证→200+JS跳转，不存在→404·1266B |
| **authserver** | authserver.ncwu.edu.cn | **基线完全未测** ★ |

**关键**：如果 news / www2 的基线与主站 **md5 相同**，说明同版本同配置 → 主站发现的洞在它们上面**同样存在**，中危可写"跨多实例普遍存在"。

---

## 三、开放探索题目（这些是我们没做的）

### 题目 1：`/system/resource/code/` 下还有什么？（用 ②vs④ 枚举）

我们只摸了 `news/click/` 一个子目录。用存在性 oracle 找其他的：

```
/system/resource/code/vote/
/system/resource/code/search/
/system/resource/code/comment/
/system/resource/code/upload/      ← 若存在且免鉴权 = 高危
/system/resource/code/counter/
```

**判据**：200 = 存在；2455B = 不存在；912B = 有锁。

### 题目 2：有没有源码/备份文件？（命中即中危以上）

博达是**闭源商业软件**，拿到 JSP 源码价值极高（可审计出真漏洞，且跨校通用）。

```
/system/resource/code/news/click/addclicktimes.jsp.bak
/system/resource/code/news/click/addclicktimes.jsp~
/system/resource/code/news/click/.addclicktimes.jsp.swp
/system/resource/code/news/click/clicktimes.jsp.bak
/system/resource/code/news/click/.DS_Store
```

**判据**：返回 200 且 Content-Type 是 `text/plain` 或内容是 JSP 源码文本 = **源码泄露**。

### 题目 3：`/system/` 下除了 `resource/` 还有没有免鉴权子树？

已知 `/system/` 主体有 912B 锁，但 `/system/resource/` 免鉴权。用 ③vs④ 找其他漏网子树：

```
/system/js/    /system/css/    /system/images/
/system/template/    /system/upload/    /system/config/
```

### 题目 4：0B 端点聚类

已知返回 0B 的：`datainput.jsp`（image/gif）、`addclicktimes.jsp` 缺参、
`clicktimes.jsp` 缺参、owner 错、type 错。

**问题**：0B 是不是一个统一的"受理无回执"通道？还有多少端点属于它？

**做法**：枚举其他路径，凡返回 200·0B 的都记下来，看能否归成一类。
**若发现某个 0B 端点实际执行了写操作**（从前端 JS 语义判断），那是新中危。

### 题目 5：news / www2 用各自 owner 复现 click 端点

已知 owner：主站 `1731478964`、news `1731479278`、www2 `1626939659`。

```
news.ncwu.edu.cn/system/resource/code/news/click/clicktimes.jsp
  ?wbnewsid=999999999&owner=1731479278&type=wbimage

www2.ncwu.edu.cn/.../clicktimes.jsp
  ?wbnewsid=999999999&owner=1626939659&type=wbimage
```

**判据**：非 912B = 该实例同样免鉴权 → 中危可写"跨三实例普遍存在"。
**注意**：用不存在的 ID（999999999），**不构成写入**。

### 题目 6：jwmis 青果的存在性 oracle（我们没系统用过）

已知：jwmis 未认证 → 200 + JS 跳转；不存在路径 → 404·**1266B**。

**这也是一个判别器**（比博达的还干净，因为 200 和 404 分得清）。用它枚举：

```
/hsjw/frame/          （已知 200）
/hsjw/js/
/hsjw/config/         （青果 filter 拦 config.properties，但这不等于整个目录都拦）
/hsjw/kingosoft/      （已知有 password/ 子目录）
/hsjw/upload/
```

**重点找**：青果各版本常有的未授权 JSP、静态资源列目录。
**若找到 `/hsjw/` 下的 `.jsp.bak` 或配置文件 = 中危以上。**

### 题目 7：authserver 的六态基线（完全没测）

authserver 与主站**同 IP 同网关**，且我们知道它放行已注册路径。但它的响应状态从未系统测绘。

```
/authserver/login             （已知 200）
/authserver/<随机串>           → ? 
/authserver/nonexistent.jsp   → ?
/authserver/serviceValidate   （已知 200，是返回身份信息的端点）
```

**问题**：authserver 有没有自己的 404 模板？和主站 1693B 一样吗？
如果不同，说明它走的是另一套处理链 —— 可能有新的可枚举面。

### 题目 8：目录列目录

```
/system/resource/code/news/click/
/system/resource/js/
```

判据：返回 200 且内容是文件列表 = 低危，但能一次性拿到完整文件清单（**极大加速题目 1、2**）。

---

## 四、硬约束（违反即作废）

| 禁止 | 原因 |
|---|---|
| ❌ 对 `addclicktimes.jsp` 发**带完整参数**的请求 | 写入后端持久化存储，永久 +1 且删不掉 |
| ❌ 对 `datainput.jsp` 发带全参数请求 | 已误触发过一次 |
| ❌ 构造 SQL 片段 / 上传 / 登录 / 爆破 | 越界 |
| ❌ 用真实存在的 ID 调 click 端点 | 可能触发计数写入 |

| 必须 | |
|---|---|
| ✅ 间隔 **≥7s**，分时段跑 | 约 3 个请求可能触发限流（同 IP 已观察到 RST→静默丢弃） |
| ✅ 记录 **Content-Length + Content-Type + 前 200 字节** | 只看状态码会误判（image/gif 那次的教训） |
| ✅ 看 **HTTP 层**响应，不看渲染结果 | 页面有 JS 跳转会误导 |
| ✅ 用**不存在的 ID**（999999999）做探测 | 避免写入 |

---

## 五、已确证事实（直接采信，别重复测）

- 参数来自目标自身 JS：`clickid` / `wbnewsid` / `wburlid` / `owner` / `type` / `clicktype` / `randomid`
- 三级状态：缺参 0B · 查无 1B `0` · 有值数字（如 `1135`）
- 脏数据 `65813abc` → 回退 `-1`（有强类型转换）
- `addclicktimes.jsp` 缺参 → 200·0B（**不是 912B**）
- `datainput.jsp` → 200·0B·**image/gif**（1×1 追踪像素，无返回面）
- 912B 是路径级拦截，**连不存在的路径也返回它**
- 非法字符（`<`、引号、反斜杠）→ 400·2304B，泄 `VAppServer/6.0.0` + `Http11InputBuffer`（Tomcat 7 标志）+ Java 8
- 网关放行前缀：`/` 、`/system/` 、`/_sitegray/` 、`/tpl-v2/`
- CustomerNO 六份证据全一致，`webber` 前缀 = 西安博达
- treeid：主站/news = 1001，www2 = 1033；owner 才是站点级区分键
- jwmis 找回密码双版均 302 弹登录，**未登录不可达**（已排除）
- authserver 忘记密码面**未启用**（HTML 注释态，已排除）

---

## 六、交付要求

请回答（**答不上就写"无法确认"，不许推测充数**）：

1. 每个面的六态基线是什么？news/www2 与主站是否 **md5 相同**？
2. `/system/resource/code/` 下还枚举出哪些子目录？有无 `upload` 类？
3. **是否拿到任何源码/备份/配置文件？**（最优先，命中即中危以上）
4. `/system/` 下还有其他免鉴权子树吗？
5. news / www2 的 click 端点是否同样免鉴权？
6. jwmis 用 200 vs 404·1266B 枚举出了什么？
7. authserver 的基线是什么，和主站一样吗？
8. **有没有我们完全没想到的发现？**（这是本次最重要的开放题）

---

## 七、定级参考（避免虚报）

| 发现 | 级别 |
|---|---|
| 状态可区分本身 | **低危**（不是中危，HTTP 差异有业务合理性） |
| 拿到 JSP 源码 / 配置文件 | **中危~高危** |
| 找到免鉴权 upload 端点 | **高危** |
| 免鉴权写接口（addclicktimes） | **中危**，但危害是"篡改公开统计数据"，不是代码执行 |

**不能写**："可写入任意数据" / "可执行代码" / "已验证存在"。
**要写**："未观察到鉴权拦截" / "未实际触发以避免修改数据"。
