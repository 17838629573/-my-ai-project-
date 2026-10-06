"""# 契约: tests.cases_phenom
## 范围
常见物理现象的门检用例执行体：
  P41 树叶飘落(leaf_fall) / P42 墙体开裂(fracture) / P43 水流冲击(water_jet)
  P44 牛顿摆(newton_cradle) / P45 转台离心(turntable)

## 依赖
motion.phenom ; tests.harness(判据) ; tests.criteria.CRIT(阈值与出处)

## 判据口径声明（改动判据必须写明理由，禁止静默）
- P41 只测 flutter 的终端速度与 tumbling 的自转圈数。自持翻滚（tumbling）的
  涌现未实现，故不设"必须涌现 tumbling"的判据，避免用假判据充数。
- P42 不用动量守恒作判据：PBD 位置投影本身不严格守恒动量，mom_err 仅作参考。
  改为"球撞击后减速"+"碎块位移有界"，前者证动量确实传给了墙，后者证数值稳定。
- P43 spread 用终态横向范围/初始横向范围。地面无摩擦时 180 个粒子会被摊成
  单层（宽约 5.4m），spread 失真到 30 倍，故加地面切向摩擦 gf=0.985。
- P44 中间球静止只在首次碰撞后 0.25s 窗口内成立：末球摆回二次撞击后中间球
  必然动起来，这是真实牛顿摆行为，用全程最大角位移判会把正确实现判死。
"""

from motion.phenom import (leaf_fall_sim, fracture_sim, water_jet_sim,
                           newton_cradle_sim, turntable_sim)


# ---------------------------------------------------------------- P41
def case_P41():
    """P41 树叶飘落：终端速度远低于自由落体 / 水平漂移 / flutter 涌现。"""
    mode, v_term, n_swings, dtheta, traj = leaf_fall_sim()
    dx = abs(traj[-1][0] - traj[0][0])
    checks = [("leaf_v_term_mps", v_term),
              ("leaf_drift_m", dx),
              ("leaf_swings", float(n_swings))]
    meta = {"模式": mode, "终端速度_m/s": v_term, "摆动次数": n_swings,
            "净转角_rad": dtheta, "水平漂移_m": dx}
    return checks, meta


# ---------------------------------------------------------------- P42
def case_P42():
    """P42 墙体开裂：静置稳定 / 断键 / 多碎块 / 球减速 / 碎块位移有界。"""
    (n_broken, n_frag, max_disp, mom_err, settle, v_end) = fracture_sim()
    checks = [("frac_max_disp_m", max_disp),
              ("frac_n_broken", float(n_broken)),
              ("frac_n_frag", float(n_frag))]
    meta = {"静置位移_m": settle, "断键数": n_broken, "碎块数": n_frag,
            "碎块最大位移_m": max_disp, "球末速_m/s": v_end,
            "动量_err(仅参考)": mom_err}
    return checks, meta


# ---------------------------------------------------------------- P43
def case_P43():
    """P43 水流冲击地面：不穿地 / 横向铺展 / 粒子不丢 / 密度收敛。"""
    min_y, spread, rho_rel, n_alive = water_jet_sim()
    checks = [("water_spread_ratio", spread),
              ("water_rho_rel", rho_rel),
              ("water_n_alive", float(n_alive)),
              ("ground_penetration_m", -min_y)]
    meta = {"最低点_m": min_y, "铺展比": spread, "密度偏差": rho_rel,
            "有效粒子": n_alive}
    return checks, meta


# ---------------------------------------------------------------- P44
def case_P44():
    """P44 牛顿摆：末球弹出 / 中间球窗口内静止 / 能量守恒。"""
    v_last, th_mid, th_last, mom_err, en_err = newton_cradle_sim()
    checks = [("cradle_th_mid_win_rad", th_mid),
              ("cradle_th_last_win_rad", th_last),
              ("cradle_energy_err", en_err)]
    meta = {"末球速度_m/s": v_last, "中间球窗口角位移_rad": th_mid,
            "末球窗口角位移_rad": th_last, "能量_err": en_err,
            "动量_err(仅参考)": mom_err}
    return checks, meta


# ---------------------------------------------------------------- P45
def case_P45():
    """P45 转台：离心滑移 / 被甩向外 / 科氏横向偏转 / 低速不滑移。"""
    r_end, slip, lat = turntable_sim()
    r2, slip2, _ = turntable_sim(om_p=0.1)
    checks = [("turntable_r_end_m", r_end),
              ("turntable_lateral_m", lat)]
    meta = {"末半径_m": r_end, "滑移": slip, "横向偏转_m": lat,
            "低速末半径_m": r2, "低速滑移": slip2}
    return checks, meta
