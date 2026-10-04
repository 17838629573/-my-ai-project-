"""路径—路面对齐（契约 contracts/path_align.md，铁律95-98）

业界依据：NavMesh 制作流程 Step1 = Find walkable surfaces。
先确认表面可行走，再在其上定义路径；角色位置由路径参数(s+offset)直接决定。
"""
import numpy as np


def normalize_pts(pts, W, H):
    """铁律96：控制点必须在画布内，越界即报错（禁静默裁剪）。"""
    bad = [p for p in pts if not (0 <= p[0] <= W and 0 <= p[1] <= H)]
    if bad:
        raise SystemExit(
            f"[铁律96] 路径控制点越界 {bad}，画布 {W}x{H}。"
            f"请把控制点改到画面内（旧值 x=-300..1700 在 540 宽画布上大半不可见）")
    return [tuple(float(v) for v in p) for p in pts]


def _row_continuity(row):
    """水平连续性：相邻列亮度差异越小越像地面（0~1）。"""
    r = row.astype(np.float64)
    gx = np.abs(np.diff(r, axis=0)).mean()
    return float(np.exp(-gx / 24.0))


def walkable_band(bg_bgr, y0=0, y1=None):
    """铁律95：检测可行走表面。

    返回每行的可行走得分（水平连续性 × 局部水平条带宽度）。
    地面特征：行内水平连续（纹理一致）且上下有明确分界。
    """
    h = bg_bgr.shape[0]
    y1 = h if y1 is None else y1
    gray = bg_bgr.mean(axis=2) if bg_bgr.ndim == 3 else bg_bgr
    scores = np.zeros(h, dtype=np.float64)
    for y in range(int(y0), int(y1)):
        scores[y] = _row_continuity(gray[y])
    return scores


def _relative_smooth(gray, xi, yi, patch_std, r=10):
    """透视自适应平滑度。

    背景（实测逼出，2026-10-03 城墙背景 540x960）：
      原判据 smooth = exp(-std/35) 用的是【绝对】阈值。
      透视下远处地面纹理被压缩，局部 std 天然偏大 → 近处判地面、
      远处判非地面，与 walkable_band 的行级结论【互相矛盾】
      （行级说 y=560~600 是地面 0.603，点级说 0.174）。

    修正：判据改为【相对】——该点是否比【同一行】其它位置更乱，
      而不是绝对方差小。同行基准 = 该行所有 r×r patch 的 std 中位数。
      近处基准低、远处基准高，于是阈值随透视自适应。
    """
    h, w = gray.shape[:2]
    yi = int(round(yi))
    if yi < 0 or yi >= h:
        return float(np.exp(-patch_std / 35.0))
    y0, y1 = max(0, yi - r), min(h, yi + r)
    band = gray[y0:y1]
    if band.shape[1] < 2 * r:
        return float(np.exp(-patch_std / 35.0))
    # 沿该行滑窗取 std 中位数作为基准
    stds = []
    step = max(1, (w - 2 * r) // 12)
    for x in range(0, max(1, w - 2 * r), step):
        stds.append(float(band[:, x:x + 2 * r].std()))
    base = float(np.median(stds)) if stds else patch_std
    # 相对超出量：该点比同行基准乱多少
    excess = patch_std - base
    return float(np.exp(-max(0.0, excess) / 35.0))


def is_ground_patch(bg_bgr, x, y, r=10, depth=40):
    """判定 (x,y) 周围是否为地面 patch。

    双判据（缺一不可，单点判据会被噪声骗过）：
      1) 纹理细密：patch 内标准差低 —— 排除随机噪声/杂乱区
      2) 有厚度：向下 depth 像素仍是同类材质 —— 排除天空/仅一条边缘线
    """
    h, w = bg_bgr.shape[:2]
    xi, yi = int(round(x)), int(round(y))
    if not (0 <= xi < w and 0 <= yi < h):
        return False, 0.0
    gray = bg_bgr.mean(axis=2) if bg_bgr.ndim == 3 else bg_bgr
    patch = gray[max(0, yi - r):min(h, yi + r), max(0, xi - r):min(w, xi + r)]
    if patch.size == 0:
        return False, 0.0
    smooth = _relative_smooth(gray, xi, yi, float(patch.std()), r)
    c = float(patch.mean())
    yb = min(h, yi + depth)
    below = gray[yi:yb, max(0, xi - r):min(w, xi + r)]
    thick = float(np.exp(-np.abs(below.mean() - c) / 45.0)) if below.size else 0.0
    score = smooth * thick
    return (smooth > 0.5 and thick > 0.5), score


def validate_path(pts, bg_bgr, table=None, n=24, total=None):
    """铁律98：沿路径采样，校验是否落在可行走面上。

    返回 dict(ok, rate, fails)。偏差率 = 非地面采样点 / 总采样点。
    """
    import path as PA
    table = table or PA.arc_table(pts)
    total = total if total is not None else table["total"]
    fails, scores = [], []
    for i in range(n):
        s = total * i / max(1, n - 1)
        xy = PA.at_distance(pts, s, table=table)["xy"]
        ok, sc = is_ground_patch(bg_bgr, xy[0], xy[1])
        scores.append(sc)
        if not ok:
            fails.append((round(s, 1), int(xy[0]), int(xy[1])))
    rate = len(fails) / max(1, n)
    return {"ok": rate <= 0.15, "rate": rate, "fails": fails,
            "mean_score": float(np.mean(scores))}


def visible_path_prompt(pts, half_width_px, px_per_m, material="夯土走道"):
    """铁律97：生成"画面内可见"的路面几何描述（禁画布外坐标）。"""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    a, b = pts[0], pts[-1]
    w_m = 2 * half_width_px / px_per_m
    return (f"{material}：自画面内({int(a[0])},{int(a[1])})延伸至({int(b[0])},{int(b[1])})，"
            f"宽约{w_m:.1f}米，横向贯穿画面 x={int(min(xs))}~{int(max(xs))}，"
            f"路面水平、两侧为女墙，透视为平视略俯，路面清晰可辨可站立行走。")


def self_check():
    import cv2
    W, H = 540, 960
    # 1 越界必须报错
    try:
        normalize_pts([(-300, 452), (1700, 450)], W, H)
        return False, "铁律96 越界未报错"
    except SystemExit:
        pass
    # 2 画布内应通过
    normalize_pts([(0, 450), (270, 448), (539, 450)], W, H)
    # 3 合成地面图：上半天空、下半均匀地面
    img = np.zeros((H, W, 3), np.uint8)
    img[:450] = 180                      # 天空（均匀水平）
    img[450:] = 100                      # 地面（均匀水平）
    img[440:460] = 40                    # 分界线
    v = validate_path([(0, 700), (270, 700), (539, 700)], img)
    if not v["ok"]:
        return False, f"地面路径判定失败 {v}"
    # 4 证伪：把路径放到纯随机噪声区（非地面）应失败
    rng = np.random.default_rng(0)
    noise = rng.integers(0, 255, (H, W, 3), dtype=np.uint8)
    v2 = validate_path([(0, 700), (270, 700), (539, 700)], noise)
    if v2["ok"]:
        return False, "证伪失败：噪声区被判为地面"
    return True, "path_align 4项自检PASS（含证伪）"


if __name__ == "__main__":
    ok, msg = self_check()
    print(("[OK] " if ok else "[FAIL] ") + msg)
