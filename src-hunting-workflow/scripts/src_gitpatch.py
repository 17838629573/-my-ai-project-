#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
src_gitpatch.py —— 静默补丁探测器 + 源码静态分析器

能力来源：GitHub API（commits / contents / search）
  api.github.com, codeload.github.com 可达；
  目标站点直连不可达时，用开源组件源码做等价分析。

核心功能：
  silent   检测「描述平淡但改动在校验/边界」的 commit —— 未认领的 1-day
  diff     取指定 commit 的完整 diff，做补丁对齐
  fetch    读取仓库任意文件原文
  grep     在源码里搜危险模式（sink 点、硬编码、危险函数）

这是工作流 P1（泛化）与 P6（补丁对齐）的执行引擎。
"""

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict

API = "https://api.github.com"
HDR = {"User-Agent": "Mozilla/5.0", "Accept": "application/vnd.github+json"}
TOKEN = os.environ.get("GITHUB_TOKEN", "")

# 描述平淡 —— 静默补丁的语言特征
VAGUE = [
    "improve", "hardening", "harden", "refactor", "cleanup", "clean up",
    "fix edge case", "edge case", "minor", "misc", "polish", "tidy",
    "update check", "improve check", "better", "robust", "robustness",
    "handle", "adjust", "tweak", "optimize", "optimise", "chore(deps)",
    "bump", "recompile", "merge pull request", "merge branch",
    "l10n", "translations", "update translations",
]

# 改动在校验/边界 —— 静默补丁的代码特征
GUARD = [
    "validate", "sanitiz", "sanitis", "escap", "check", "verify", "deny",
    "reject", "forbidden", "unauthorized", "authoriz", "permission",
    "allow", "whitelist", "blocklist", "blacklist", "bound", "limit",
    "overflow", "underflow", "truncat", "clamp", "strip", "filter",
    "normaliz", "canonical", "path traversal", "cors", "csrf", "token",
    "signature", "hmac", "nonce", "session", "rate limit", "quota",
]

# 危险 sink —— 静态分析找汇聚点
SINK = [
    ("命令执行", r"\b(exec|system|passthru|shell_exec|popen|proc_open|eval)\s*\("),
    ("反序列化", r"\b(unserialize|pickle\.loads|yaml\.load|readObject)\s*\("),
    ("文件包含", r"\b(include|require|include_once|require_once)\s*\(?\s*\$"),
    ("SQL拼接", r"(SELECT|INSERT|UPDATE|DELETE)[^\"']{0,80}\"\s*\.\s*\$|f\"[^\"]*(SELECT|INSERT|UPDATE|DELETE)"),
    ("SSRF出口", r"\b(curl_setopt|file_get_contents|fsockopen|requests\.(get|post)|fetch)\s*\("),
    ("任意文件读", r"\b(file_get_contents|fopen|readFile|open)\s*\(\s*\$"),
    ("模板注入", r"\b(render_template_string|Template)\s*\("),
    ("硬编码密钥", r"(?i)(api[_-]?key|secret|password|passwd|token|private[_-]?key|access[_-]?key)\s*[:=]\s*[\"'][A-Za-z0-9_\-/+]{12,}"),
    ("AWS密钥", r"AKIA[0-9A-Z]{16}"),
    ("私钥", r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    ("JWT硬编码", r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\."),
    ("调试开关", r"(?i)(debug|DEBUG)\s*[:=]\s*(true|1)\b"),
]

# 噪音目录：编译产物 / 依赖 / 翻译
NOISE = re.compile(
    r"(^|/)(dist|build|vendor|node_modules|3rdparty|\.git|locale|l10n|"
    r"tests?|__tests__|\.map|package-lock|composer\.lock|"
    r"\.min\.(js|css)|\.chunk\.|coverage)/?|\.(map|lock|po|mo|svg|png|jpg)$",
    re.I)


def api(path, retry=3):
    url = f"{API}{path}"
    h = dict(HDR)
    if TOKEN:
        h["Authorization"] = f"Bearer {TOKEN}"
    last = None
    for i in range(retry):
        try:
            r = urllib.request.Request(url, headers=h)
            return json.loads(urllib.request.urlopen(r, timeout=30).read())
        except Exception as e:
            last = e
            code = getattr(e, "code", None)
            if code == 403:  # rate limit
                time.sleep(3 * (i + 1))
                continue
            if code == 404:
                return None
            time.sleep(1.5)
    print(f"[!] API 失败 {path}: {last}", file=sys.stderr)
    return None


def is_vague(msg):
    m = (msg or "").lower()
    return any(v in m for v in VAGUE)


def is_guard(patch):
    p = (patch or "").lower()
    return sum(1 for g in GUARD if g in p)


def cmd_silent(a):
    """检测静默补丁：描述平淡 + 改动在校验/边界"""
    print(f"[*] 扫描 {a.repo} 的最近 {a.n} 个 commit")
    print(f"[*] 路径过滤: {a.path or '全部（自动排除噪音目录）'}\n")
    path_q = f"&path={urllib.parse.quote(a.path)}" if a.path else ""
    commits = api(f"/repos/{a.repo}/commits?per_page={min(a.n,100)}{path_q}") or []
    print(f"[+] 取到 {len(commits)} 个 commit，逐个取 diff 分析...\n")

    cands = []
    for c in commits:
        sha = c["sha"]
        msg = c["commit"]["message"].split("\n")[0]
        d = api(f"/repos/{a.repo}/commits/{sha}")
        if not d:
            continue
        files = [f for f in d.get("files", [])
                 if not NOISE.search(f.get("filename", ""))]
        if not files:
            continue
        hits = []
        for f in files:
            g = is_guard(f.get("patch", ""))
            if g >= a.guard:
                hits.append((f["filename"], g,
                             f.get("additions", 0), f.get("deletions", 0)))
        if not hits:
            continue
        vague = is_vague(msg)
        score = sum(h[1] for h in hits) * (30 if vague else 0)
        if not vague:
            continue  # 只留描述平淡的 —— 已认领的修复价值低
        hits.sort(key=lambda x: -x[1])
        cands.append({"sha": sha[:10], "msg": msg, "score": score,
                      "files": hits[:5], "date": c["commit"]["author"]["date"][:10],
                      "url": c["html_url"]})
        time.sleep(0.4)

    cands.sort(key=lambda x: -x["score"])
    print("=" * 74)
    print(f" 静默补丁候选：{len(cands)} 个（描述平淡 + 改动在校验/边界）")
    print("=" * 74)
    if not cands:
        print("\n 无命中。可放宽 --guard（默认 2）或扩大 --n。")
        return 0
    for c in cands[:a.top]:
        print(f"\n● [{c['score']}分] {c['sha']}  {c['date']}")
        print(f"  描述: {c['msg'][:100]}")
        for fn, g, add, dele in c["files"]:
            print(f"    +{add}/-{dele}  守卫分{g}  {fn}")
        print(f"  {c['url']}")
    print("\n 判定：这些是**未公开认领**的安全修复候选 —— 竞争几乎为零。")
    print("      下一步：取 diff 看具体加了什么检查，再写 PoC。")
    print(f"      命令：python3 src_gitpatch.py diff --repo {a.repo} --sha <sha>")
    if a.out:
        json.dump(cands, open(a.out, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        print(f"\n[+] 已写入 {a.out}")
    return 0


def cmd_diff(a):
    d = api(f"/repos/{a.repo}/commits/{a.sha}")
    if not d:
        print("取不到该 commit")
        return 1
    msg = d["commit"]["message"]
    print(f"[*] {a.sha[:12]}  {msg.splitlines()[0][:100]}")
    print(f"[*] 作者: {d['commit']['author']['name']}  "
          f"日期: {d['commit']['author']['date'][:10]}")
    print(f"[*] 变更文件: {len(d.get('files',[]))}\n")
    for f in d.get("files", []):
        fn = f.get("filename", "")
        if NOISE.search(fn) and not a.all:
            continue
        print("=" * 70)
        print(f"FILE: {fn}  (+{f.get('additions',0)}/-{f.get('deletions',0)})")
        print("=" * 70)
        print((f.get("patch") or "(无 patch，可能是二进制)")[:a.maxlen])
        print()
    return 0


def cmd_fetch(a):
    d = api(f"/repos/{a.repo}/contents/{a.path}")
    if not d:
        print("取不到该文件")
        return 1
    if isinstance(d, list):
        for x in d:
            print(f"{x['type']:5} {x['name']}")
        return 0
    if d.get("encoding") == "base64":
        content = base64.b64decode(d["content"]).decode("utf-8", "replace")
    else:
        content = d.get("content", "")
    print(content[:a.maxlen])
    return 0


def cmd_grep(a):
    """在源码里搜危险模式。用 code search API；无 token 时退化为逐个文件抓取。"""
    print(f"[*] 在 {a.repo} 搜索危险模式\n")
    if TOKEN:
        results = defaultdict(list)
        for name, pat in SINK:
            q = urllib.parse.quote(f"{a.query} repo:{a.repo}")
            r = api(f"/search/code?q={q}&per_page=20")
            if not r or "items" not in r:
                continue
            for it in r["items"]:
                results[name].append(it["path"])
            time.sleep(1)
        for name, paths in results.items():
            print(f"\n● {name}: {len(paths)} 处")
            for p in paths[:8]:
                print(f"   {p}")
    else:
        print("[!] 未设 GITHUB_TOKEN，代码搜索 API 不可用（未认证限流）。")
        print("[*] 退化为：遍历目录 + 逐文件正则匹配（慢但可用）\n")
        files = api(f"/repos/{a.repo}/git/trees/{a.branch}?recursive=1")
        if not files:
            print("取不到目录树")
            return 1
        tree = [t for t in files.get("tree", [])
                if t["type"] == "blob" and not NOISE.search(t["path"])]
        if a.path:
            tree = [t for t in tree if t["path"].startswith(a.path)]
        tree = tree[:a.limit]
        print(f"[*] 检查 {len(tree)} 个文件\n")
        found = defaultdict(list)
        for t in tree:
            d = api(f"/repos/{a.repo}/contents/{urllib.parse.quote(t['path'])}")
            if not d or d.get("encoding") != "base64":
                continue
            try:
                src = base64.b64decode(d["content"]).decode("utf-8", "replace")
            except Exception:
                continue
            for name, pat in SINK:
                for m in re.finditer(pat, src):
                    line = src[:m.start()].count("\n") + 1
                    snippet = src.splitlines()[line - 1].strip()[:120]
                    found[name].append((t["path"], line, snippet))
                    break
            time.sleep(0.15)
        if not found:
            print(" 未命中任何危险模式（也可能是文件数太少）")
        for name, hits in found.items():
            print(f"\n● {name}: {len(hits)} 处")
            for p, ln, sn in hits[:10]:
                print(f"   {p}:{ln}")
                print(f"      {sn}")
    return 0


def main():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repo", required=True, help="owner/repo")

    ap = argparse.ArgumentParser(description="GitHub 源码静态分析：静默补丁/补丁diff/危险模式")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("silent", parents=[common], help="检测静默补丁（描述平淡+改动在校验）")
    s.add_argument("--n", type=int, default=60)
    s.add_argument("--path", help="限定路径，如 lib/")
    s.add_argument("--guard", type=int, default=2, help="守卫词命中阈值")
    s.add_argument("--top", type=int, default=12)
    s.add_argument("--out")
    s.set_defaults(func=cmd_silent)

    s = sub.add_parser("diff", parents=[common], help="取 commit 的 diff")
    s.add_argument("--sha", required=True)
    s.add_argument("--maxlen", type=int, default=3000)
    s.add_argument("--all", action="store_true", help="不过滤噪音目录")
    s.set_defaults(func=cmd_diff)

    s = sub.add_parser("fetch", parents=[common], help="读文件原文")
    s.add_argument("--path", required=True)
    s.add_argument("--maxlen", type=int, default=8000)
    s.set_defaults(func=cmd_fetch)

    s = sub.add_parser("grep", parents=[common], help="搜危险模式")
    s.add_argument("--query", default="")
    s.add_argument("--path", help="限定路径前缀")
    s.add_argument("--branch", default="master")
    s.add_argument("--limit", type=int, default=120)
    s.set_defaults(func=cmd_grep)

    a = ap.parse_args()
    sys.exit(a.func(a) or 0)


if __name__ == "__main__":
    main()
