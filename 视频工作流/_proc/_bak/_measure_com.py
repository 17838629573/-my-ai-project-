# -*- coding: utf-8 -*-
"""实测全身 COM（Winter/Dempster 体段质量分数加权），比对文献区间。
不假设对称：左右腿/上下半周分别统计。
"""
import numpy as np, math, character as C

H = 1.70
# Winter 1990 / Dempster 体段质量分数（每条肢体）
M = {"thigh":0.100, "shank":0.0465, "foot":0.0145,
     "upperarm":0.028, "forearm":0.016, "hand":0.006}
M_HAT = 0.678                       # head+arms+trunk
M_ARM = M["upperarm"]+M["forearm"]+M["hand"]
M_TH  = M_HAT - 2*M_ARM             # 去掉双臂后的躯干+头
# 段 COM 从近端起的比例
K = {"thigh":0.433, "shank":0.433, "foot":0.500,
     "upperarm":0.436, "forearm":0.430}

def seg_com(a, b, k):
    return a + k*(b-a)

def com_of(J):
    """J: gait() 输出（归一化身高）→ 全身 COM"""
    tot = np.zeros(3); msum = 0.0
    for side in ("l","r"):
        hip, knee, ank, toe = J["hip_"+side], J["knee_"+side], J["ank_"+side], J["toe_"+side]
        for name, (a,b) in {"thigh":(hip,knee), "shank":(knee,ank), "foot":(ank,toe)}.items():
            c = seg_com(a, b, K[name]); tot += M[name]*c; msum += M[name]
        sh, elb, wri = J["sh_"+side], J["elb_"+side], J["wri_"+side]
        c = seg_com(sh, elb, K["upperarm"]); tot += M["upperarm"]*c; msum += M["upperarm"]
        # hand 合并进 forearm（无腕外关节）
        c = seg_com(elb, wri, K["forearm"]); tot += (M["forearm"]+M["hand"])*c; msum += M["forearm"]+M["hand"]
    # 躯干+头：由 HAT 表值反解（HAT COM 从大转子 0.626×HAT段长）
    hat_len = C.PROP["shoulder"] - C.PROP["hip"]          # 0.818-0.520
    p_hat_v = C.PROP["hip"] + 0.626*hat_len
    v = np.array([J["chest"][0], p_hat_v + (J["chest"][1]-C.PROP["chest"]), J["chest"][2]])
    tot += M_TH*v; msum += M_TH
    return tot/msum

N = 360
C3 = np.array([com_of(C.gait(i/N)) for i in range(N)]) * H
u, v, w = C3[:,0], C3[:,1], C3[:,2]

print("质量校验 Σm = %.4f (应=1.000)" % (2*sum(M[k] for k in ("thigh","shank","foot")) + 2*M_ARM + M_TH))
print()
print("全身 COM 实测（文献区间对照）")
print("  v 垂直  峰峰 %.4f m   文献 ~0.050 m   每周期2次" % np.ptp(v))
print("  w 侧向  峰峰 %.4f m   文献 0.040~0.060 m  每周期1次" % np.ptp(w))
print("  u 前后  峰峰 %.4f m   应≈0（匀速前进，不叠正弦）" % np.ptp(u))
print()
# 不对称：上下半周分别统计（真实步态左右步不完全相同）
half = N//2
print("不对称性检查（前半周 vs 后半周，真实人不会完全相等）")
print("  v 峰高  前 %.4f  后 %.4f   差 %.4f m" % (v[:half].max(), v[half:].max(), abs(v[:half].max()-v[half:].max())))
print("  w 极值  前 %+.4f  后 %+.4f  差 %.4f m" % (w[:half].max(), w[half:].min(), abs(w[:half].max()+w[half:].min())))
print()
# 侧向每周期几次振荡（文献=1次）
dw = np.diff(np.sign(np.diff(w)))
print("  w 每周期极值次数 = %d（文献要求 1）" % len([1 for i,x in enumerate(dw) if x!=0]))
dv = np.diff(np.sign(np.diff(v)))
print("  v 每周期极值次数 = %d（文献要求 2）" % len([1 for i,x in enumerate(dv) if x!=0]))
