"""跳帧扫描器：逐帧量化视频帧间差，定位硬跳帧

契约: proc/jumpscan
  输入: mp4 路径
  输出: {'diffs':[...], 'top':[(frame_idx, diff)], 'ratio': 最大/中位}
  依赖: cv2 numpy
  被依赖: 无
  约束: 只读分析，不修改任何渲染代码；判据为"单帧差 > 5倍中位差"视为硬跳
  校验: python3 jumpscan.py <mp4>
"""
import sys, os, numpy as np, cv2

def scan(path, max_frames=1200):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return {"error": "cannot open " + path}
    prev = None
    diffs = []
    n = 0
    while n < max_frames:
        ok, fr = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY).astype(np.float32)
        if prev is not None:
            diffs.append(float(np.abs(g - prev).mean()))
        prev = g
        n += 1
    cap.release()
    if len(diffs) < 3:
        return {"error": "too few frames", "n": len(diffs)}
    a = np.array(diffs)
    med = float(np.median(a))
    mx = float(a.max())
    idx = int(np.argmax(a))
    # 找出所有超过 5 倍中位的帧
    thr = max(med * 5.0, 1.0)
    bad = [(int(i), float(a[i])) for i in np.where(a > thr)[0]]
    return {"n": len(diffs), "median": med, "max": mx, "max_frame": idx,
            "ratio": (mx / med) if med > 1e-9 else float('inf'),
            "bad": bad[:12], "bad_count": len(bad)}

if __name__ == "__main__":
    for p in sys.argv[1:]:
        r = scan(p)
        print(os.path.basename(p), r)
