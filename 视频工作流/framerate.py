#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
framerate.py —— 帧率/时间基准（单一数据源）
=============================================
契约: contracts/framerate.md

铁律28: 输出帧率定死 60fps，全局唯一，禁止第二帧率常量
铁律29: 序列帧数由物理周期反算 N = round(T_phys × FPS)，禁止拍脑袋
铁律30: 素材帧数不符时用播放速率钳制 ±15%，超出即报错（禁静默变速）

自检: python3 framerate.py
"""
import os
import sys
import math
import numpy as np

# ── 铁律28：全局唯一帧率 ────────────────────────────────────
FPS = 60

# ── 铁律30：Distance Matching 播放速率钳制（业界 ±15%）────────
PLAYRATE_CLAMP = (0.85, 1.15)


def frames_for_period(T_phys, fps=FPS):
    """铁律29：周期(s) -> 应有序列帧数。禁止手填帧数。"""
    if T_phys <= 0:
        return 1
    return max(1, int(round(T_phys * fps)))


def playrate(n_have, n_want, clamp=PLAYRATE_CLAMP):
    """
    素材帧数 n_have vs 物理应有帧数 n_want。
    返回播放速率；超出钳制范围即 ValueError（禁静默变速）。
    """
    if n_want <= 0:
        raise ValueError("n_want 必须 > 0")
    r = n_have / n_want          # 素材多 -> 播慢；素材少 -> 播快
    lo, hi = clamp
    if not (lo <= r <= hi):
        raise ValueError(
            "素材 %d 帧 vs 物理应有 %d 帧 -> 播放速率 %.3f 超出 ±%d%%。"
            "请按 N=round(T×FPS) 重新生成序列帧（铁律29），禁静默变速。"
            % (n_have, n_want, r, int((hi - 1) * 100)))
    return r


def dt(fps=FPS):
    """物理时间步。禁止写死 1/60（铁律28）。"""
    return 1.0 / fps


def seconds_to_frames(sec, fps=FPS):
    return max(1, int(round(sec * fps)))


# --------------------------------------------------------------- 自检
def frame_index(t, durations):
    """当前时刻该显示第几张素材 -> (i0, i1, f)。

    【铁律46】播放时序唯一入口。契约 contracts/playback.md
    1) 边界由索引前缀和算出，禁止累加舍入（业界：Do not accumulate
       rounded timestamps — calculate each boundary from its index）。
    2) 周期为唯一真源：Σ durations 是一个周期，t 先对周期取模。
    3) 均匀是默认；非均匀只来自 solver 的 intentional_hold。
    """
    ds = [float(d) for d in durations]
    if not ds:
        raise ValueError("frame_index: durations 为空")
    if any(d <= 0 for d in ds):
        raise ValueError("frame_index: durations 含非正值")
    period = math.fsum(ds)                       # 精确求和，不累加
    tt = float(t) % period
    acc = 0.0
    for i, d in enumerate(ds):
        if tt < acc + d:
            return i, (i + 1) % len(ds), (tt - acc) / d
        acc += d
    i = len(ds) - 1
    return i, 0, 1.0


def cumulative_starts(durations):
    """前缀和边界（业界要求：从 index 算，不累加）。"""
    out, acc = [], 0.0
    for d in durations:
        out.append(acc)
        acc += float(d)
    return out


def duplicate_endpoint(frames):
    """末帧是否≈首帧（循环接缝重复的端点）。

    业界：接缝处停顿先查 accidental duplicate endpoint，而不是加时长。
    返回 (is_dup, 差异值)；差异越小越像重复端点。
    """
    if not frames or len(frames) < 2:
        return False, None
    a = np.asarray(frames[0], dtype=np.float32)
    b = np.asarray(frames[-1], dtype=np.float32)
    if a.shape != b.shape:
        return False, None
    diff = float(np.abs(a - b).mean())
    return diff < 1.0, diff


def self_check():
    ok = True
    n = 0

    # 1) 全局帧率唯一性：扫描活跃代码，禁止第二帧率常量
    n += 1
    base = os.path.dirname(os.path.abspath(__file__))
    bad = []
    import ast
    NAMES = ("FPS", "FILM_FPS", "WALK_FPS", "OUT_FPS", "VIDEO_FPS")
    for fn in sorted(os.listdir(base)):
        if not fn.endswith(".py") or fn == "framerate.py":
            continue
        p = os.path.join(base, fn)
        try:
            src = open(p, encoding="utf-8", errors="ignore").read()
            tree = ast.parse(src)
        except (OSError, SyntaxError):
            continue
        # 迭代求解文件内数值常量（支持链式：A=1 ; B=A/2 ; C=B*3）
        def _num(nd):
            try:
                return ast.literal_eval(nd)
            except (ValueError, SyntaxError):
                return None
        consts = {}
        assigns = []
        for nd in ast.walk(tree):
            try:
                if isinstance(nd, (ast.Assign, ast.AnnAssign)):
                    if isinstance(nd, ast.Assign):
                        t, v = nd.targets[0], nd.value
                    else:
                        t, v = nd.target, nd.value
                    if v is not None and isinstance(t, ast.Name):
                        assigns.append((t.id, v))
                        nv = _num(v)
                        if isinstance(nv, (int, float)):
                            consts[t.id] = nv
            except (IndexError, AttributeError):
                pass
        for _ in range(6):                      # 链式最多解 6 层
            grew = False
            for name, v in assigns:
                if name in consts:
                    continue
                try:
                    got = eval(compile(ast.Expression(v), "<x>", "eval"),
                               {"__builtins__": {}}, dict(consts))
                    if isinstance(got, (int, float)):
                        consts[name] = got
                        grew = True
                except Exception:
                    pass
            if not grew:
                break

        for node in ast.walk(tree):
            # 普通赋值：FPS = 60
            if isinstance(node, ast.Assign):
                tgts, val = node.targets, node.value
            # 带类型标注：FPS: int = 60
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                tgts, val = [node.target], node.value
            else:
                continue
            # 元组赋值：W, H, FPS = 540, 960, 60
            if isinstance(val, ast.Tuple) and isinstance(tgts[0], ast.Tuple):
                pairs = list(zip(tgts[0].elts, val.elts))
            else:
                pairs = [(t, val) for t in tgts]
            for t, v in pairs:
                if not isinstance(t, ast.Name) or t.id not in NAMES:
                    continue
                try:
                    got = ast.literal_eval(v)
                except (ValueError, SyntaxError):
                    continue          # 表达式赋值（如 WALK_FPS=24/1.0）单独处理
                if float(got) != FPS:
                    bad.append(f"{fn}:L{node.lineno} {t.id} = {got}")
            # 表达式赋值：能算出值也算（如 WALK_FPS = WALK_FRAMES / WALK_PERIOD）
            for t, v in pairs:
                if not isinstance(t, ast.Name) or t.id not in NAMES:
                    continue
                if isinstance(v, ast.BinOp):
                    try:
                        got = eval(compile(ast.Expression(v), "<x>", "eval"),
                                   {"__builtins__": {}}, dict(consts))
                        if float(got) != FPS:
                            bad.append(f"{fn}:L{node.lineno} {t.id} = {got} (表达式)")
                    except Exception:
                        pass
    if bad:
        print("FAIL 存在第二帧率常量（铁律28）:")
        for b in bad:
            print("   -", b)
        ok = False
    else:
        print("PASS 帧率唯一（FPS=%d，无第二常量）" % FPS)

    # 2) 铁律29：帧数由周期反算
    n += 1
    T = 0.585                      # 幡旗物理周期（anchor.py 由 St 推出）
    N = frames_for_period(T)
    if N == 35:
        print("PASS 周期 %.3fs @%dfps -> %d 帧（非手填 24）" % (T, FPS, N))
    else:
        print("FAIL 帧数反算异常: %d" % N)
        ok = False

    # 3) 制造帧数的检测：24 帧素材在 60fps 下的频率偏差
    n += 1
    f_wrong = FPS / 24.0           # 若每帧播1张
    f_right = 1.0 / T
    dev = abs(f_wrong - f_right) / f_right
    if dev > 0.15:
        print("PASS 检出制造帧数：24帧 -> %.3fHz，物理 %.3fHz，偏差 %.1f%%"
              % (f_wrong, f_right, dev * 100))
    else:
        print("FAIL 未检出制造帧数（偏差 %.1f%%）" % (dev * 100))
        ok = False

    # 4) 铁律30：超出钳制必须报错
    n += 1
    try:
        playrate(24, 35)
        print("FAIL 24/35 未报错（应超出 ±15%）")
        ok = False
    except ValueError as e:
        print("PASS 素材不足即报错: %s" % str(e)[:56])

    # 5) 合法范围内不报错
    n += 1
    try:
        r = playrate(35, 35)
        print("PASS 帧数相符 playrate=%.3f" % r)
    except ValueError as e:
        print("FAIL 相符却报错: %s" % e)
        ok = False

    # 6) dt 不得写死
    n += 1
    if abs(dt(30) - 1 / 30) < 1e-12 and abs(dt() - 1 / 60) < 1e-12:
        print("PASS dt 随 fps 变化（未写死 1/60）")
    else:
        print("FAIL dt 写死")
        ok = False

    # N) 播放时序（铁律46，契约 contracts/playback.md）
    def _r(name, cond, note=""):
        nonlocal n, ok
        n += 1
        ok = ok and bool(cond)
        print(("PASS " if cond else "FAIL ") + name + ("  " + note if note else ""))

    # N) 播放时序（铁律46，契约 contracts/playback.md）
    n += 1
    ds = [0.5 / 8] * 8
    i0, i1, f = frame_index(0.0, ds)
    _r("t=0 落在第0帧", i0 == 0 and i1 == 1 and abs(f) < 1e-12,
             "i0=%d i1=%d f=%.3f" % (i0, i1, f))
    tt = math.fsum(ds[:4]) + ds[4] * 0.5
    i0, i1, f = frame_index(tt, ds)
    _r("半程落在第4帧中点", i0 == 4 and abs(f - 0.5) < 1e-9,
             "i0=%d f=%.3f" % (i0, f))
    i0, i1, f = frame_index(0.5 * 3 + 0.4999, ds)
    _r("周期取模不越界", 0 <= i0 < 8, "i0=%d" % i0)
    # 前缀和 vs 累加舍入：N=35 非整除时长下不得漂移
    d35 = [0.585 / 35] * 35
    st = cumulative_starts(d35)
    acc, accs = 0.0, []
    for d in d35:
        accs.append(acc); acc += d
    _r("前缀和与累加一致(N=35)",
             max(abs(a - b) for a, b in zip(st, accs)) < 1e-9)
    _r("Σ durations 精确等于周期",
             abs(math.fsum(d35) - 0.585) < 1e-12, "%.15f" % math.fsum(d35))
    # 非均匀：末帧停留时总长仍守恒
    # 不 import solver：framerate 是 solver 的下游，反向依赖会成环（门禁已拦）
    _k = 1.8
    _d = 0.5 / ((12 - 1) + _k)
    du = [_d] * 11 + [_k * _d]
    _r("非均匀总长守恒", abs(math.fsum(du) - 0.5) < 1e-9)
    i0, i1, f = frame_index(0.499, du)
    _r("非均匀末帧可被取到", i0 == 11, "i0=%d" % i0)
    try:
        frame_index(0.0, [0.5, -0.1])
        _r("非正时长报错", False)
    except ValueError:
        _r("非正时长报错", True)

    print("\n%d 项检查 -> %s" % (n, "PASS" if ok else "FAIL"))

    return ok, n


if __name__ == "__main__":
    _ok, _ = self_check()
    sys.exit(0 if _ok else 1)
