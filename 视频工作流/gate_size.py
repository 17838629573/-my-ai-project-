"""产物体积门禁：防止媒体产物无上限增长（回归过两次）"""
import os, subprocess

# 阈值：目录超过即 FAIL
LIMIT_MB = {
    "_out32": 0,      # 可再生原始帧，禁止存在
    "_raw": 60, "_chk": 40, "_生成": 80,
    "assets_tang": 100, "shots_tang": 40, "shots": 30,
    "audio": 20, "_旗帧": 10, "_seg_v4": 10, "_骨架": 5,
}
# 同名历史目录只允许保留一份（历代切分产物并存过 6 份）
DUPLICATE_GROUPS = [["_segments", "_seg", "_seg_v3", "_seg_v4"]]

def dir_mb(d):
    if not os.path.isdir(d):
        return 0.0
    r = subprocess.run(["du", "-sm", d], capture_output=True, text=True)
    return float(r.stdout.split()[0]) if r.stdout else 0.0

def self_check():
    ok = True
    for d, lim in LIMIT_MB.items():
        mb = dir_mb(d)
        if mb > lim:
            print(f"FAIL 体积超限 {d}: {mb}MB > {lim}MB")
            ok = False
    for grp in DUPLICATE_GROUPS:
        exist = [d for d in grp if os.path.isdir(d)]
        if len(exist) > 1:
            print(f"FAIL 历史目录并存 {exist}（只允许保留一份）")
            ok = False
    if ok:
        print("PASS 产物体积门禁")
    return ok

if __name__ == "__main__":
    raise SystemExit(0 if self_check() else 1)
