# photo_rules 改动史

## headroom 偏离业界（实测 6/8 偏离）

业界 house-style：景别越紧 headroom 越小。
Wide/establishing 15-20%｜Medium 10-12%｜CU 5-8%｜ECU 近 0。

初版实测偏离：

| 景别 | 初版 | 业界 | |
|---|---|---|---|
| EWS | 37.5% | 10-25% | 近 2 倍 |
| CU | 11.0% | 5-8% | 偏大 |
| ECU | 8.5% | 0-5% | 偏大 |

已按上表纠正，现 8/8 达标。

## 三字段矛盾（架构级，实测）

`headroom + body_frac + footroom` 必须 = 1.0，但三者各自手填：

```
EWS  0.170 + 0.25 + 0.375 = 0.795   → 声明17%，实际渲染38%，差21pt
WS   0.175 + 0.50 + 0.170 = 0.845
FS   0.125 + 0.72 + 0.115 = 0.960
```

后果：`body_pixels` 用 `body_frac`、`ground_y` 用 `footroom`，
实际头顶留白被算出来，与声明值不符。

修法：全身景别 footroom 改为由 `1 - headroom - body_frac` 派生。
现 3/3 守恒，渲染值与声明值逐位吻合。
