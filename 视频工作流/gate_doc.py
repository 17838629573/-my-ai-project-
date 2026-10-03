"""文档体积门禁：防止主干/契约无限膨胀（瘦身成果已回归两次）"""
import os, glob

LIMIT = {
    "WORKFLOW.md": 8000,        # 主干只做路由，超标即回归
    "WORKFLOW_S1_生成前.md": 30000,
    "WORKFLOW_S2_生成后.md": 30000,
    "WORKFLOW_S3_复盘.md": 30000,
}
CONTRACT_LIMIT = 4000   # 单份契约上限
CONTRACT_TOTAL = 70000  # 契约总量上限

def sz(p):
    """字符数，非字节数。

    口径依据（与 gate_module.py 的 len(src) 一致）：
    对 LLM 而言真实上下文占用是字符/token，不是磁盘字节。
    中文 UTF-8 一个汉字占 3 字节，用 getsize 会把中文文档虚高约 1.6 倍，
    导致阈值实际上被压到原意的三分之一（历史 bug，已修）。
    """
    if not os.path.exists(p):
        return 0
    with open(p, encoding="utf-8") as f:
        return len(f.read())

def self_check():
    ok = True
    for f, lim in LIMIT.items():
        n = sz(f)
        if n > lim:
            print(f"FAIL 主干超限 {f}: {n} > {lim}")
            ok = False
    for f in sorted(glob.glob("contracts/*.md")):
        n = sz(f)
        if n > CONTRACT_LIMIT:
            print(f"FAIL 契约超限 {f}: {n} > {CONTRACT_LIMIT}")
            ok = False
    tot = sum(sz(f) for f in glob.glob("contracts/*.md"))
    if tot > CONTRACT_TOTAL:
        print(f"FAIL 契约总量 {tot} > {CONTRACT_TOTAL}")
        ok = False
    else:
        print(f"  契约总量 {tot} / {CONTRACT_TOTAL}")
    if ok:
        print("PASS 文档体积门禁")
    return ok

if __name__ == "__main__":
    raise SystemExit(0 if self_check() else 1)
