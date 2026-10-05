# IMPROVE · contact_plan.py 改前必读

Status: Accepted（2026-10-04）· Supersedes: 无

## 真坑（踩过，别重犯）

### 坑1：contact 与 separation 是两类约束，不能合并成一张表
- contact_list：关节对，距离应 ≈ 0（贴住）
- separation_list：关节对，距离须 > contact_threshold（防穿模）
两者语义相反。合并处理会在"距离恰好等于阈值"时判定互斥振荡。

### 坑2：contact_bound 是帧区间，不是瞬时值
接触发生在 [ts, te] 区间内。旧代码只判单帧，导致接触在窗口内时断时续。
窗口换算（帧→时间）必须用 framerate，禁手填。

### 坑3：持有锁必须在中断时释放
第 10 项自检专门锁这个：中断后 release，占用表必须归零 {}。
漏释放会让第二次交互永远拿不到锁（静默失效，极难排查）。

## 依据
- InterControl：把交互建成 Contact Plan（contact_list / separation_list / contact_bound）

## 实测（self_check，10 项全过）
```
6 区间内生效      7 区间外不生效
8 接触窗口换算 (30, 45)
9 持有锁          10 中断后释放锁 {}
```
