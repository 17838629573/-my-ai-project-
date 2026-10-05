"""推送项目到 GitHub —— 整包替换「视频工作流」目录

契约: tools/push_gh
  输入: TOKEN(环境变量 GH_TOKEN 或内置)、本地项目根目录
  输出: commit sha + 远程校验(文件数/类型统计)
  依赖: 标准库 urllib/json/base64/pathlib/concurrent
  被依赖: 人工执行(无代码引用)
  约束: 排除 mp4/mov/avi/webm/mkv/m4v/flv(产物, 不入库)
        排除 pyc/pyo/__pycache__/_bak(缓存与过程备份)
        整包替换: 远程「视频工作流」子树整体换新 sha, 不留旧残留
        低并发(3)+429/403 指数退避, 规避 GitHub 二级限流
  校验: 运行后自动拉取远程 tree 比对文件数
"""
from __future__ import annotations
import base64, hashlib, json, os, sys, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# 安全约定: token 只从环境变量读取, 脚本内不留明文(避免自身被推送时泄露)
TOKEN = os.environ.get("GH_TOKEN", "").strip()
if not TOKEN:
    raise SystemExit("请设置 GH_TOKEN 环境变量后运行")
OWNER, REPO, BRANCH = "17838629573", "-my-ai-project-", "main"
SUBDIR = "视频工作流"
ROOT = Path(__file__).resolve().parent

EXCLUDE_EXT = {".mp4", ".mov", ".avi", ".webm", ".mkv", ".m4v", ".flv",
               ".pyc", ".pyo", ".so", ".zip",
               ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff"}
EXCLUDE_PART = {"__pycache__", ".git", "_bak", ".venv", "node_modules"}
MAX_PER_RUN = 50

API = "https://api.github.com"
HDR = {"Authorization": f"Bearer {TOKEN}",
       "Accept": "application/vnd.github+json",
       "X-GitHub-Api-Version": "2022-11-28",
       "User-Agent": "yuanbao-push"}


def _req(method, path, body=None, tries=5):
    data = json.dumps(body).encode() if body is not None else None
    last = None
    for i in range(tries):
        r = urllib.request.Request(API + path, data=data, headers=HDR, method=method)
        try:
            with urllib.request.urlopen(r, timeout=120) as f:
                raw = f.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            last = e
            body_txt = e.read().decode()[:200]
            if e.code in (403, 429) or "rate limit" in body_txt.lower():
                w = min(60, 5 * (2 ** i))
                print(f"  [限流] {e.code} 退避 {w}s ({i+1}/{tries})")
                time.sleep(w)
                continue
            raise RuntimeError(f"{method} {path} -> {e.code}: {body_txt}")
        except Exception as e:
            last = e
            time.sleep(2)
    raise RuntimeError(f"{method} {path} 失败: {last}")


def collect():
    out = []
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if any(x in rel.parts for x in EXCLUDE_PART):
            continue
        if p.suffix.lower() in EXCLUDE_EXT:
            continue
        out.append((str(rel).replace(os.sep, "/"), p))
    return out


def main():
    files = collect()
    print(f"本地待推 {len(files)} 个文件")
    if not files:
        print("无文件"); return 1

    ref = _req("GET", f"/repos/{OWNER}/{REPO}/git/ref/heads/{BRANCH}")
    base_sha = ref["object"]["sha"]
    base = _req("GET", f"/repos/{OWNER}/{REPO}/git/commits/{base_sha}")
    base_tree = base["tree"]["sha"]
    print(f"基点 commit {base_sha[:8]}")

    # 1) blobs —— 分批续传(规避单批大量请求触发沙箱限制)
    CACHE = Path("/data/workspace/.gh_blobs.json")
    blobs = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    # 缓存键带内容哈希：只按路径缓存会让改过的文件一直复用旧 sha（同 .done 只查存在不校验内容）
    def _ckey(rel, p):
        h = hashlib.sha1(p.read_bytes()).hexdigest()[:12]
        return rel + "#" + h
    todo = [(r, p) for r, p in files if _ckey(r, p) not in blobs]
    print(f"待传 {len(todo)} / 共 {len(files)}（已缓存 {len(blobs)}）")
    if todo:
        batch = todo[:MAX_PER_RUN]
        def up(item):
            rel, p = item
            b = _req("POST", f"/repos/{OWNER}/{REPO}/git/blobs",
                     {"content": base64.b64encode(p.read_bytes()).decode(),
                      "encoding": "base64"})
            return rel, b["sha"]
        with ThreadPoolExecutor(max_workers=2) as ex:
            for n, ((rel, p), (_, sha)) in enumerate(zip(batch, ex.map(up, batch)), 1):
                blobs[_ckey(rel, p)] = sha
                if n % 20 == 0 or n == len(batch):
                    print(f"  blob {n}/{len(batch)}")
        CACHE.write_text(json.dumps(blobs))
    # 回映成 路径->sha，供建 tree 使用
    rel2sha = {}
    for r, p in files:
        k = _ckey(r, p)
        if k in blobs:
            rel2sha[r] = blobs[k]
    remain = len(files) - len(rel2sha)
    if remain > 0:
        print(f"\n本批完成，尚余 {remain} 个 —— 再跑一次本脚本继续")
        return 0
    print(f"blob 全部就绪 {len(rel2sha)}")
    blobs = rel2sha

    # 2) 逐目录建 tree（自底向上，确保二级路径也登记）
    # 自底向上: 深层目录先建, 父目录才能引用到子目录的 tree sha
    dirs = sorted({os.path.dirname(r) for r in blobs if os.path.dirname(r)},
                  key=lambda d: (-d.count("/"), d))
    tree_sha = {}
    for d in dirs:
        entries = []
        # 本层直属文件
        for rel, sha in blobs.items():
            if os.path.dirname(rel) == d:
                entries.append({"path": os.path.basename(rel), "mode": "100644",
                                "type": "blob", "sha": sha})
        # 直属子目录
        subs = {x[len(d)+1:].split("/")[0] for x in blobs
                if x.startswith(d + "/") and "/" in x[len(d)+1:]}
        for s in sorted(subs):
            entries.append({"path": s, "mode": "040000", "type": "tree",
                            "sha": tree_sha[d + "/" + s]})
        t = _req("POST", f"/repos/{OWNER}/{REPO}/git/trees", {"tree": entries})
        tree_sha[d] = t["sha"]

    top = []
    for rel, sha in blobs.items():
        if "/" not in rel:
            top.append({"path": rel, "mode": "100644", "type": "blob", "sha": sha})
    for s in sorted({r.split("/")[0] for r in blobs if "/" in r}):
        top.append({"path": s, "mode": "040000", "type": "tree", "sha": tree_sha[s]})
    new_tree = _req("POST", f"/repos/{OWNER}/{REPO}/git/trees", {"tree": top})
    print(f"子目录树 {len(dirs)} 个, 根树 {new_tree['sha'][:8]}")

    # 3) 整包替换：把 SUBDIR 指向新树，其余保留
    parent_entries = [{"path": SUBDIR, "mode": "040000", "type": "tree",
                       "sha": new_tree["sha"]}]
    try:
        cur = _req("GET", f"/repos/{OWNER}/{REPO}/git/trees/{base_tree}")
        for e in cur.get("tree", []):
            if e["path"] != SUBDIR:
                parent_entries.append({"path": e["path"], "mode": e["mode"],
                                       "type": e["type"], "sha": e["sha"]})
    except Exception as e:
        print(f"  [warn] 读根树失败 {e}")

    parent_tree = _req("POST", f"/repos/{OWNER}/{REPO}/git/trees",
                       {"tree": parent_entries})
    c = _req("POST", f"/repos/{OWNER}/{REPO}/git/commits", {
        "message": f"修A4转身: 峰值角速度纳入约束(1020->460dps, ISBS2015), M_A 0.9->0.6; jitter_px口径错用改peak_rate_dps; PASS21/FAIL0",
        "tree": parent_tree["sha"], "parents": [base_sha]})
    _req("PATCH", f"/repos/{OWNER}/{REPO}/git/refs/heads/{BRANCH}",
         {"sha": c["sha"]})
    print(f"\ncommit {c['sha']}")
    print(f"https://github.com/{OWNER}/{REPO}/commit/{c['sha']}")

    # 4) 校验
    time.sleep(2)
    chk = _req("GET", f"/repos/{OWNER}/{REPO}/git/trees/{c['sha']}?recursive=1")
    items = chk.get("tree", [])
    sub = [i for i in items if i["path"].startswith(SUBDIR + "/")]
    vids = [i for i in sub if i["path"].lower().endswith(
        (".mp4", ".mov", ".avi", ".webm", ".mkv", ".m4v", ".flv"))]
    pycs = [i for i in sub if i["path"].endswith(".pyc")]
    print(f"\n远程校验: {SUBDIR} 下 {len(sub)} 个文件")
    print(f"  视频 {len(vids)}  pyc {len(pycs)}")
    ext = {}
    for i in sub:
        e = Path(i["path"]).suffix.lower() or "(无)"
        ext[e] = ext.get(e, 0) + 1
    print("  " + "  ".join(f"{k}={v}" for k, v in
                           sorted(ext.items(), key=lambda x: -x[1])[:8]))
    ok = len(vids) == 0 and len(pycs) == 0 and len(sub) == len(files)
    print(f"\n{'✅ 通过' if ok else '⚠️ 需检查'}: 本地 {len(files)} vs 远程 {len(sub)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
