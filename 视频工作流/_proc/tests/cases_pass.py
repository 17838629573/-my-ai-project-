"""D22 两人传球 用例

契约: tests/cases_pass
  输入: 无（用例自带固定参数；两人间距与时序取自 motion.character.pass_ball）
  输出: (checks, extra)——checks 交 harness.report，extra 为补充事实
  依赖: numpy, motion.character.pass_ball/ball/render, motion.run, tests.gen, tests.harness
  被依赖: tests/run_all
  约束: 渲染一律走 tests.gen.render_case（内部为 run.draw_actor 单一管线），
        第二人画在 extra 回调内（人物掩膜已于 extra 之前取，避免球/第二人污染剪影判据）；
        判据阈值一律取自 harness.CRIT，不许就地拍数
  校验: python -m tests.run_all
"""
import os
import numpy as np
from motion.character import pass_ball as PB
from motion.character import ball as _B
from motion.character import render as _CR
from motion import run as R
import tests.gen as G_
import tests.harness as H

OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS = 60.0
# 相机距离：D_APART=3.5m，Z=5 时屏幕跨度约 617px > 画面宽 540px 会出画，故取 Z=8
ZC = 8.0
HAND_LOD = 1


def _ball_at(p_m, cv, cam, zc):
    """额外绘制球：世界坐标(米) -> 投影 -> SDF 圆（与 cases_throw._ball_at 同口径，zc 参数化）"""
    W, HH = G_.W, G_.HH
    bh = G_.BODY_H

    def pr(x):
        return _CR.project_body({"b": (x[0] / bh, x[1] / bh, 0.0)},
                                cam, Xc=0.0, Zc=zc, yaw=90.0, body_h=bh)["b"]

    P0 = pr(p_m)
    P1 = pr((p_m[0] + _B.R_BALL, p_m[1]))
    r = max(abs(P1[0] - P0[0]), 2.0)
    gy, gx = np.mgrid[0:HH, 0:W]
    d = np.sqrt((gx - P0[0]) ** 2 + (gy - P0[1]) ** 2) - r
    m = d < 0
    a = np.asarray(cv.img).astype(np.float32)
    shade = np.clip(0.72 + 0.28 * (-d / max(r, 1e-6)), 0, 1)[..., None]
    a[m] = np.array([226, 224, 218], np.float32) * shade[m]
    a[np.abs(d) < 1.2] = np.array([70, 66, 60], np.float32)
    cv.set_arr(a)


def _flight_vx_err(t0, t1, n=24):
    """飞行段水平速度守恒相对误差（水平方向无外力，vx 应恒定）"""
    ts = np.linspace(t0, t1, n)
    xs = np.array([PB.ball_world(t)[0] for t in ts])
    vx = np.diff(xs) / np.diff(ts)
    return float((vx.max() - vx.min()) / max(abs(vx.mean()), 1e-12))


def case_D22():
    """两人传球：A 投 -> B 接 -> B 投回 -> A 接

    依据: Peper et al. 1994 tau 时间-接触信息（手与球同时到达）；
    Belousov et al. NIPS 2016 预测性接球（反应时间与任务时长比值）；
    篮球双手胸前传球教学（两人一组相距 3-5m）
    """
    n = int(round(PB.T_TOTAL * FPS))

    def pose(t):
        return PB.pose_A(min(t / PB.T_TOTAL, 1.0))

    def extra(t, cv, cam):
        tc = min(t / PB.T_TOTAL, 1.0)
        R.draw_actor(cv, cam, PB.pose_B(tc), Xc=PB.XC_B, Zc=ZC,
                     yaw=PB.YAW_B, body_h=G_.BODY_H,
                     template="humanoid", hand_lod=HAND_LOD)
        _ball_at(PB.ball_world(tc), cv, cam, ZC)

    r = G_.render_case("D22", pose, n, "D22_两人传球",
                       yaw=PB.YAW_A, Zc=ZC, lane=PB.XC_A,
                       t_end=PB.T_TOTAL, hand_lod=HAND_LOD, extra=extra)
    # 接触：球心与接球手应重合（未接触就抓取 = 穿模）
    pen = max(float(np.linalg.norm(PB.ball_world(PB.T_ARRIVE1)
                                   - PB.hand_world(PB.T_ARRIVE1))),
              float(np.linalg.norm(PB.ball_world(PB.T_ARRIVE2)
                                   - PB.hand_world(PB.T_ARRIVE2))))
    # 飞行段水平速度守恒（两程方向相反，分段量，避免正负跨越虚高）
    mom = max(_flight_vx_err(PB.T_REL_A, PB.T_ARRIVE1),
              _flight_vx_err(PB.T_REL_B, PB.T_ARRIVE2))
    vals = dict(r["vals"])
    vals["penetration_m"] = pen
    vals["momentum_err"] = mom
    checks = [(k, v) for k, v in vals.items()]
    _, ok = H.report(checks)
    ts = np.linspace(0.0, PB.T_TOTAL, 400)
    return (checks, {"ok": ok, "mp4": r["mp4"], "png": r["png"],
                     "ball_min_y": float(min(PB.ball_world(t)[1] for t in ts)),
                     "D_apart": float(PB.D_APART)})
