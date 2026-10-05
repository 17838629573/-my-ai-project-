"""_camera 自检（独立模块，避免撑大核心文件）

证伪原则：只测"能算出来"不算通过，必须证明错误输入会被拦。
"""
from __future__ import annotations
import math
import _camera as C

FAILS = []


def ck(cond, msg):
    if cond:
        print("  PASS %s" % msg)
    else:
        FAILS.append(msg)
        print("  FAIL %s" % msg)
    return cond


def main():
    H, W = 960, 540
    f = C.focal_px(H)

    print("[1] 景别闭合：解出的距离使主体像高 = tau*H")
    subj = {"h_m": 1.70, "y_base_m": 0.0, "z_m": 30.0, "x_m": 0.0}
    for name in ("ELS", "LS", "FS", "MCU", "ECU"):
        cam = C.solve(subj, shot_size=name, angle="eye", image_w=W, image_h=H)
        rho = cam["rho"]
        px_h = f * subj["h_m"] / rho          # 针孔像高
        want = cam["tau"] * H
        ck(abs(px_h - want) < 0.5,
           "%s 像高%.1fpx == tau*H=%.1fpx" % (name, px_h, want))

    print("[2] 景别单调：ELS 最远，ECU 最近")
    ds = [C.solve(subj, shot_size=n, image_h=H)["rho"]
          for n in ("ELS", "LS", "FS", "MCU", "ECU")]
    ck(all(ds[i] > ds[i + 1] for i in range(len(ds) - 1)),
       "距离递减 ELS..ECU: %s" % [round(d, 1) for d in ds])

    print("[3] 角度单调：low < eye < high < bird 的相机高")
    hs = [C.camera_height_for_angle(0.0, 1.70, a)
          for a in ("low", "eye", "high", "bird")]
    ck(all(hs[i] < hs[i + 1] for i in range(len(hs) - 1)),
       "h_cam 递增: %s" % [round(h, 2) for h in hs])

    print("[4] 地平线：俯仰角越大(越俯视)，地平线越靠画面上方")
    vhs, ps = [], []
    for ang in ("low", "eye", "high", "bird"):
        cam = C.solve(subj, shot_size="LS", angle=ang, image_h=H)
        vhs.append(cam["v_h"])
        ps.append(cam["pitch_rad"])
    ck(all(vhs[i] > vhs[i + 1] for i in range(len(vhs) - 1)),
       "v_h 随俯视递减: %s" % [round(v, 1) for v in vhs])
    ck(all(ps[i] < ps[i + 1] for i in range(len(ps) - 1)),
       "pitch 随机位升高递增: %s" % [round(math.degrees(p), 1) for p in ps])

    print("[5] 地平线自洽：无穷远地面点投影 y ≈ v_h")
    cam = C.solve(subj, shot_size="LS", angle="high", image_h=H)
    far = C.project_point(0.0, 0.0, cam["z_cam"] + 1e7,
                          cam["h_cam"], cam["z_cam"], cam["pitch_rad"],
                          W, H, cam["f_px"])
    ck(far is not None and abs(far[1] - cam["v_h"]) < 1.0,
       "无穷远地面 y=%.1f ≈ v_h=%.1f" % (far[1], cam["v_h"]))

    print("[6] pitch 收敛：主体中心投影到 v_target")
    cam = C.solve(subj, shot_size="FS", angle="eye", image_h=H,
                  v_target_ratio=0.55)
    p = C.project_point(0.0, 0.85, subj["z_m"], cam["h_cam"], cam["z_cam"],
                        cam["pitch_rad"], W, H, cam["f_px"])
    ck(p is not None and abs(p[1] - 0.55 * H) < 1.0,
       "主体中心 v=%.1f ≈ 0.55H=%.1f" % (p[1], 0.55 * H))

    print("[7] 证伪：相机在物体后方必须报不可见，不得返回伪坐标")
    bad = {"name": "身后物", "h_m": 2.0, "y_base_m": 0.0,
           "z_m": cam["z_cam"] - 5.0, "x_m": 0.0}
    ok, rep = C.visibility_report(cam, [bad])
    ck((not ok) and rep[0]["bottom_v"] is None,
       "相机后方物体报不可见且不返回坐标")

    print("[8] 证伪：非法景别/角度必须抛错，不得静默降级")
    for fn, args in ((lambda: C.solve(subj, shot_size="XXX"), ()),
                     (lambda: C.camera_height_for_angle(0, 1.7, "worm"), ())):
        try:
            fn()
            ck(False, "非法输入应抛错")
        except (KeyError, ValueError):
            ck(True, "非法输入抛错")

    print("[9] 核心：共现约束有区分力 —— 网格上既有成功也有失败")
    # 僧人在 12m 墙顶马道(z=40)，柳树在地面(z=35，介于相机与僧人之间)
    monk = {"name": "僧人", "h_m": 1.70, "y_base_m": 12.0, "z_m": 40.0, "x_m": 0.0}
    tree = {"name": "柳树", "h_m": 6.00, "y_base_m": 0.0, "z_m": 35.0, "x_m": 8.0}
    okc = failc = 0
    for sz in C.SHOT_SIZE:
        for ang in C.ANGLE:
            for sc in (1.0, 12.0):
                cam = C.solve(monk, shot_size=sz, angle=ang,
                              image_w=W, image_h=H, dist_scale=sc)
                ok, _ = C.visibility_report(cam, [monk, tree])
                okc += ok
                failc += (not ok)
    print("     网格 5景别×4角度×2退远：成功%d 失败%d" % (okc, failc))
    ck(okc > 0 and failc > 0,
       "约束有区分力(非恒通/恒不通)：成功%d 失败%d" % (okc, failc))

    print("[10] 核心：solve_coappear 自动解出可行机位，不需人选 A/B/C")
    best = C.solve_coappear(monk, [monk, tree], image_w=W, image_h=H)
    ok, rep = C.visibility_report(best, [monk, tree])
    ck(ok, "自动解出 %s/%s h=%.2fm pitch=%.1f° v_h=%.1f"
       % (best["shot_size"], best["angle"], best["h_cam"],
          best["pitch_deg"], best["v_h"]))
    for r in rep:
        print("       %s: 底v=%.0f 顶v=%.0f %s"
              % (r["name"], r["bottom_v"], r["top_v"], r["issue"]))

    print("[11] 证伪：受限(max_scale=1)时无解须抛错并给原因，不得返伪机位")
    try:
        C.solve_coappear(monk, [monk, tree], image_w=W, image_h=H,
                         max_scale=1.0)   # 不许退远 → 该场景必然无解
        ck(False, "无解应抛错")
    except ValueError as e:
        ck("无可行机位" in str(e) and len(str(e)) > 50,
           "抛错并附原因: %s..." % str(e)[:90])
    ck(all(r["ok"] for r in
           C.solve_coappear(monk, [monk, tree], image_w=W,
                            image_h=H)["_report"]),
       "放宽退远后同一场景可解 —— 证伪确由约束引起，非场景本身不可拍")

    print("[12] 证伪：失败项须给可执行信息(越界量/方位)，不得只报 False")
    cam_x = C.solve(monk, shot_size="ECU", angle="eye", image_w=W, image_h=H)
    _, rep_x = C.visibility_report(cam_x, [monk, tree])
    bad = [r for r in rep_x if not r["ok"]]
    ck(bool(bad) and any(
        ("超出" in r["issue"]) or ("后方" in r["issue"]) for r in bad),
       "失败项给具体原因: %s" % (bad[0]["issue"] if bad else "无"))

    print("\n%d 项失败" % len(FAILS))
    return len(FAILS) == 0


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
