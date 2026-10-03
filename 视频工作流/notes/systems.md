# systems 改动史

## 走路循环常量（初版全错）

| 项 | 初版 | 纠正后 | 依据 |
|---|---|---|---|
| 循环 | 8 帧 @10fps = 0.8s | 24 帧 @24fps = 1.0s（12 帧/步） | anim.works：12 帧/步为中性标准 |
| 步距 | 0.75 m（拍的） | 0.765 m = 身高1.70 × 0.45 | 健走科普标准 |
| 播放速率钳制 | 无 | ±15%，超出容忍打滑 | UE Distance Matching / Lyra |

初版 8 帧/循环 @10fps 实际等于 **4 帧/步**，比"急促"档还快一倍。

## 重心起伏不随人物缩放（"一蹦一蹦"根因）

初版写死 `body_lift * 6.0` px。远景小人物 134px 时，6px 起伏占比过大 → 剧烈弹跳。

改按身高比例 `COM_V_RATIO = 0.012`（单侧）。
文献：行走 CoM 垂直波动 **2-5 cm**（约身高 1.2%-3%）。

第一版取 0.018 → 峰峰 6.1cm，**超文献上限 5cm**，改 0.012 → 4.1cm 落中位。

另加 `HEAD_STEADY = 0.35`：头部反向补偿，保持相对稳定
（业界 "keep the head comparatively steady"）。

## 走路腿部插值必须线性

业界明确：腿部用**线性**插值。在每个关键姿态加缓动会让脚"犹豫"
（hyperPad 教程原文：strong easing at every contact makes the character hesitate）。
