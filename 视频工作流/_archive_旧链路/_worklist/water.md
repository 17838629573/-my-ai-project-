# FILL water   缺 5 槽位   （模型只填 pick，勿写散文）

## 处境 (context)
已填: 无
  [water.py:L9] ---------------- 常量（唯一定义，业务模块禁重写） ----------------
  pick: water.py:9

## 决定 (decided)
已填: 无
  [IMPROVE:IMPROVE_water.md:L8] 核心答案是：**用无量纲数做桥，用少数经验公式做底。**
  [IMPROVE:IMPROVE_water.md:L10] | 现象 | 业界做法 | 我们落地 |
  [IMPROVE:IMPROVE_water.md:L28] ## 三、必须提醒 AI 做的（程序做不到）
  [IMPROVE:IMPROVE_water.md:L42] 混用会让滴数差一个量级。我们统一用**直径版** `N0=8000 m^-3 mm^-1`。
  [IMPROVE:IMPROVE_water.md:L43] 3. **Strouhal 那套不能拿来算雨。** 上轮旗帜的错误就是误用涡脱落频率；
  pick: IMPROVE_water.md:8

## 否决方案 (neglected)
已填: 无
  [IMPROVE:IMPROVE_water.md:L4] > 原则：**程序能算的交给程序；程序算不了的，写成 `[必做]` 提醒输出给 AI。**
  pick: IMPROVE_water.md:43

## 收益 (achieve)
已填: 无
  [IMPROVE:IMPROVE_water.md:L4] > 原则：**程序能算的交给程序；程序算不了的，写成 `[必做]` 提醒输出给 AI。**
  [IMPROVE:IMPROVE_water.md:L6] ## 一、业界怎么做到"公式不多、能覆盖很多情况"
  [IMPROVE:IMPROVE_water.md:L21] 倾斜角自动从 0° 变到 45°。这正回答"是不是几个系数就能表现很多种情况"：**是。**
  [IMPROVE:IMPROVE_water.md:L38] 1. **终速模型不能只留一个。** Uplinger 对 5mm 大滴准（9.15 vs Gunn-Kinzer 9.09），
  [IMPROVE:IMPROVE_water.md:L43] 3. **Strouhal 那套不能拿来算雨。** 上轮旗帜的错误就是误用涡脱落频率；
  pick: IMPROVE_water.md:21

## 代价 (accepting)
已填: 无
  [IMPROVE:IMPROVE_water.md:L14] | 普通雨 vs 风吹雨 | **同一个公式**，只差倾斜角 `α=arctan(v_wind/U)` | `rain_inclination` |
  [IMPROVE:IMPROVE_water.md:L40] （自检要求 1–3mm 内两者差 <15%）。
  [IMPROVE:IMPROVE_water.md:L42] 混用会让滴数差一个量级。我们统一用**直径版** `N0=8000 m^-3 mm^-1`。
  [IMPROVE:IMPROVE_water.md:L43] 3. **Strouhal 那套不能拿来算雨。** 上轮旗帜的错误就是误用涡脱落频率；
  [IMPROVE:IMPROVE_water.md:L46] 重力波相反。混为一谈涟漪会朝错误方向跑。
  pick: IMPROVE_water.md:40
