"""B10 扔球 / B11 接球 用例

契约: tests/cases_throw
  输入: 无（用例自带固定参数）
  输出: (checks, extra)——checks 交 harness.report，extra 为补充事实
  依赖: numpy, motion.character.throw/catch/ball, motion.rigid, tests.gen
  被依赖: tests/run_all
  约束: 渲染一律走 tests.gen.render_case（内部是 run.draw_actor 单一管线），
        不许另写画人的代码；判据阈值一律取自 harness.CRIT，不许就地拍数
  校验: python -m tests.run_all
"""
import os
import numpy as np
import motion.rigid as RG
from motion.character import ball as _B
from motion.character.body import render as _CR
import tests.gen as G_

OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS = 60.0


def _ball_at(p_m, cv, cam):
    """额外绘制球：世界坐标(米) -> 投影 -> SDF 圆（与 gen._ball_extra 同口径）"""
    W, HH = G_.W, G_.HH
    bh = G_.BODY_H
    P0 = _CR.project_body({"b": (p_m[0] / bh, p_m[1] / bh, 0.0)},
                          cam, Xc=0.0, Zc=G_.render_case.__defaults__[1],
                          yaw=90.0, body_h=bh)["b"]
    P1 = _CR.project_body({"b": ((p_m[0] + _B.R_BALL) / bh, p_m[1] / bh, 0.0)},
                          cam, Xc=0.0, Zc=G_.render_case.__defaults__[1],
                          yaw=90.0, body_h=bh)["b"]
    r = max(abs(P1[0] - P0[0]), 2.0)
    gy, gx = np.mgrid[0:HH, 0:W]
    d = np.sqrt((gx - P0[0]) ** 2 + (gy - P0[1]) ** 2) - r
    m = d < 0
    a = np.asarray(cv.img).astype(np.float32)
    shade = np.clip(0.72 + 0.28 * (-d / max(r, 1e-6)), 0, 1)[..., None]
    a[m] = np.array([226, 224, 218], np.float32) * shade[m]
    a[np.abs(d) < 1.2] = np.array([70, 66, 60], np.float32)
    cv.set_arr(a)


def case_B10():
    """扔球：动力链顺序加速->出手->弹道->落地反弹

    依据: Fleisig 动力链(stride->骨盆->躯干->伸肘->肩内旋->腕屈)，末端最快；
    出手后球为解析抛物线，二次拟合系数 a 应 = -g/2
    """
    from motion.character import throw as TH
    n = int(round(TH.T_TOTAL * FPS))

    def pose(t):
        return TH.throw(min(t / TH.T_TOTAL, 1.0))

    def extra(t, cv, cam):
        _ball_at(TH.ball_center(min(t / TH.T_TOTAL, 1.0)), cv, cam)

    r = G_.render_case("B10", pose, n, "B10_扔球",
                       t_end=TH.T_TOTAL, extra=extra)
    v = r["vals"]

    # --- 弹道：二次拟合 a = -g/2 ---
    T, P = TH._traj()
    Y = np.asarray(P)[:, 1]
    idx = len(T)
    for i in range(1, len(T)):
        if Y[i] <= _B.R_BALL + 1e-6 and Y[i] < Y[i - 1]:
            idx = i
            break
    a = float(np.polyfit(T[:idx + 1], Y[:idx + 1], 2)[0])
    gerr = abs(a - (-RG.G / 2.0)) / (RG.G / 2.0)

    # --- 释放前：球被握住，球心与手心重合（不脱手、不穿透） ---
    pen = 0.0
    for i in range(n):
        t = i / (n - 1)
        if t <= TH.F_REL:
            pen = max(pen, float(np.linalg.norm(
                TH.hand_center(t) - TH.ball_center(t))))

    # --- 球不穿地 ---
    pen_g = max(0.0, _B.R_BALL - float(np.min(Y)))

    # --- 帧间不跳变（球心位移） ---
    bc = [TH.ball_center(i / (n - 1)) for i in range(n)]
    disp = [float(np.linalg.norm(bc[i + 1] - bc[i])) for i in range(n - 1)]

    import tests.harness as H
    checks = [("flight_g_err", gerr),
              ("penetration_m", pen),
              ("ground_penetration_m", pen_g),
              ("frame_jump_ratio", H.frame_jump_ratio(disp)),
              ("silhouette_gap_px", v["silhouette_gap_px"]),
              ("silhouette_span_ratio", v["silhouette_span_ratio"])]
    rv = TH.release_vel()
    return checks, {"mp4": r["mp4"],
                    "mask_iou_参考(含球体故偏低)": round(v["mask_iou"], 4),
                    "出手速度_mps": round(float(np.linalg.norm(rv)), 3),
                    "出手仰角_deg": round(float(np.degrees(
                        np.arctan2(rv[1], rv[0]))), 1),
                    "飞行段拟合a": round(a, 4),
                    "理论-a_g/2": round(-RG.G / 2, 4)}


def case_B11():
    """接球：预测拦截点 -> 最小急动度伸手 -> 接触后球停并随手

    依据: Flash & Hogan 1985 最小急动度模型(5次多项式)；采用预测策略
    (先移到预估拦截点 IP)而非匹配球速策略，故速度单峰
    """
    from motion.character import catch as CT
    n = int(round(CT.T_TOTAL * FPS))

    def pose(t):
        return CT.catch(min(t / CT.T_TOTAL, 1.0))

    def extra(t, cv, cam):
        _ball_at(CT.ball_center(min(t / CT.T_TOTAL, 1.0)), cv, cam)

    r = G_.render_case("B11", pose, n, "B11_接球",
                       t_end=CT.T_TOTAL, extra=extra)
    v = r["vals"]

    ts = [i / (n - 1) for i in range(n)]
    hands = [CT.hand_center(t) for t in ts]
    balls = [CT.ball_center(t) for t in ts]

    # 接触后球必须随手（跟随误差）
    fol = 0.0
    for t, h, b in zip(ts, hands, balls):
        if t >= CT.F_CATCH:
            fol = max(fol, float(np.linalg.norm(np.array(h) - np.array(b))))

    # 拦截点在臂展内
    import tests.harness as H
    sh = np.array([0.0, CT._SH_Y]) * CT.H_M
    ip = CT.intercept_point()
    reach = H.arm_reach(sh, np.array(ip), CT.H_M)

    disp = [float(np.linalg.norm(np.array(balls[i + 1])
                                 - np.array(balls[i]))) for i in range(n - 1)]

    checks = [("penetration_m", fol),
              ("arm_reach", reach),
              ("frame_jump_ratio", H.frame_jump_ratio(disp)),
              ("silhouette_gap_px", v["silhouette_gap_px"]),
              ("silhouette_span_ratio", v["silhouette_span_ratio"])]
    return checks, {"mp4": r["mp4"],
                    "mask_iou_参考(含球体故偏低)": round(v["mask_iou"], 4),
                    "拦截点_m": [round(float(x), 3) for x in ip],
                    "接触后跟随误差_m": round(fol, 6)}
