# 源码级静态分析实证：Nextcloud 静默补丁

> 方法：GitHub API 拿源码与 commit diff（目标站点直连不可达，但开源组件源码可达）
> 工具：`src_gitpatch.py`（本轮新建）

---

## 直接回答

| 类别 | 数量 | 说明 |
|---|---|---|
| **明确漏洞** | **0 个** | 下面解释为什么 |
| **疑似漏洞** | **1 个** | 第三方 Share Provider 未同步哈希状态检查 |
| **方法验证** | **成功** | 静默补丁检测法首次实证有效 |

**没有明确漏洞，原因要说清楚：我分析的是厂商已经修完的补丁，不是新洞。**

但这次跑通了一件更重要的事——**证明了"静默补丁"检测法真的能挖出东西**。

---

## 一、工具能力（本轮新建）

之前我说拿不到源码，是只测了目标站点。**GitHub 系域名在白名单内**：

| 域名 | 状态 | 能做什么 |
|---|---|---|
| `api.github.com` | ✅ 200 | 列目录、读文件（base64）、取 commit 与 diff |
| `codeload.github.com` | ✅ 200 | 下载整个仓库（实测 103MB） |
| `raw.githubusercontent.com` | ⚠️ 不稳定 | 时通时断，改用 contents API 更稳 |
| 目标站点（*.gleague.nba.com 等） | ❌ 403 | `policy_default_denied`，不可达 |

`src_gitpatch.py` 四个子命令：`silent` / `diff` / `fetch` / `grep`

---

## 二、静默补丁检测：首次实证

对 `nextcloud/server` 扫最近 40 个 commit，筛选「描述平淡 + 改动在校验/边界」。

**结果噪音不小**（CSS 编译产物误判，需优化过滤），但捞到了真货：

```
● [90分] dcd254e340  2026-09-30
  Merge pull request #64908 from nextcloud/fix/session_regenerate_session_id
    +4/-1  守卫分3  lib/private/User/Session.php

● [60分] ee1feb833b  2026-09-21
  refactor: Cleanup share password hash handling
    +15/-6  守卫分2  lib/private/Share20/Manager.php
```

第二条是典型样本——**叫"重构清理"，改的是共享密码哈希**。取 diff 验证。

---

## 三、ee1feb833b 深度拆解

### 三层拆解

**触发条件层**：创建/更新共享时设置密码。

**根因层**：原代码用 `empty()` 判断密码，无法区分三种状态：

```php
// 修复前
$password = $share->getPassword() ?: '';        // null 和 '' 被合并
if (!empty($password)) {
    $share->setPassword($this->hasher->hash($password));
}
```

问题在于：**系统没有任何地方记录"这个密码是否已哈希"**。
`getPassword()` 返回的可能是明文也可能是哈希，调用方**无法区分**，全靠调用链顺序的约定来保证。

**模式层**：状态不变量缺失 —— 这正是我们工作流 P7 的抽象。
对象有一个隐含状态（已哈希/未哈希），但没有显式的状态标记，只能靠约定。

### 修复方式

引入两个新 API（`@since 35.0.0`）：

```php
public function setPasswordHash(string $passwordHash): IShare;
public function isPasswordHashed(): bool;
```

并在关键路径加不变量检查：

```php
if ($share->getPassword() !== null && !$share->isPasswordHashed()) {
    throw new RuntimeException('The password must be hashed already.');
}
```

`Share.php` 里默认值也很关键：

```php
private bool $isPasswordHashed = false;   // 新建对象默认为"未哈希"
```

**这说明 35.0.0 之前，整个共享密码系统没有哈希状态标记。**

---

## 四、外推：同步情况逐项核对 ★

按工作流「同族扩展」维度，查了所有 Share Provider：

| 文件 | 是否同步 `isPasswordHashed` 检查 | 结论 |
|---|---|---|
| `lib/private/Share20/DefaultShareProvider.php` | ✅ 3 处（140/141/142、295/296/297、1143） | 已同步 |
| `apps/sharebymail/lib/ShareByMailProvider.php` | ✅ 已同步 | 已同步 |
| `lib/private/Share20/Manager.php` | ✅ 已同步 | 已同步 |
| `apps/federatedfilesharing/.../FederatedShareProvider.php` | — 无密码调用 | 不涉及 |
| **`lib/public/Share/IShareProvider.php`** | **❓ 公开接口** | **这是缺口所在** |

### 疑似漏洞（1 个）

**假设**：`IShareProvider` 是 `lib/public/` 下的**公开接口**，第三方 app 可实现自己的 Share Provider。
这些第三方实现**不会自动获得** `isPasswordHashed` 检查——接口契约新增了状态不变量，
但既有实现没有强制同步机制。

**理论依据**：
- `Share.php` 默认 `isPasswordHashed = false`
- 核心 provider 靠新增的 throw 来拦住"未哈希密码入库"
- **第三方 provider 若不检查，未哈希密码就会直接入库**
- Nextcloud 有大量第三方 app，G 端部署常装定制 share provider

**状态**：待验证 —— 我没有环境装 app 实测

**验证步骤**（授权实例）：
1. 装一个实现了 `IShareProvider` 的第三方 app（如某个定制 share 插件）
2. 创建带密码的共享，抓包看 `share` 表写入的 password 字段
3. **命中判据**：数据库里 password 字段是明文（非 bcrypt/argon 格式）
4. **排除判据**：字段已是哈希格式，或该 app 自行调用了 `setPasswordHash()`

**为什么这条有价值**：这不是"可能存在"，是有明确的代码依据——
接口新增了状态不变量，但同步依赖各实现自觉。这正是我们工作流里
"策略只在入口检查、不在最终消费点检查"的模式。

---

## 五、诚实的边界说明

**这不是我发现的新漏洞。** 我分析的是厂商 2026-09-21 已经合入的补丁。
提交给 HackerOne 会被判重复/已知。

**这次真正的产出是方法验证**：

1. 静默补丁检测法**第一次实证有效** —— 从 40 个 commit 里，靠"描述平淡+改动在守卫"
   捞出了 `refactor: Cleanup share password hash handling` 这种真货
2. 拿到了可操作的外推假设 1 条
3. 建立了源码级分析工具链

**同时暴露了工具缺陷**：
- CSS/编译产物误判严重（`core/css/*.css` 被算成守卫改动）
- 需要更强的路径过滤和文件类型白名单
- `raw.githubusercontent.com` 不稳定，要全程走 contents API

---

## 六、下一步

**你可以直接做的**：
```bash
# 对任意开源目标扫静默补丁
python3 src_gitpatch.py silent --repo owner/repo --n 60 --guard 2

# 取某个 commit 的 diff 做补丁对齐
python3 src_gitpatch.py diff --repo owner/repo --sha <sha>

# 读任意文件
python3 src_gitpatch.py fetch --repo owner/repo --path lib/xxx.php
```

设 `GITHUB_TOKEN` 环境变量可解锁代码搜索 API（未认证时限流很严）。

**建议方向**：
1. 挑 HackerOne 公开项目里的**开源组件**（Nextcloud / MongoDB 相关 / Gitea）
2. 扫静默补丁 —— 竞争几乎为零的 1-day 来源
3. 对命中的做外推：同根因的其他实现是否同步

**目标站点源码仍需你提供**（右键查看源代码贴给我），那个我确实抓不到。
