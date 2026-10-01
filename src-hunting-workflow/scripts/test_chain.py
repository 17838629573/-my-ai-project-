#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单进程跑通：起 mock server -> 调各 rk_* 工具 -> 关闭"""
import threading, subprocess, sys, os, json, time
from http.server import HTTPServer
sys.path.insert(0, "/data/workspace")
import mock_target as M

srv = HTTPServer(("127.0.0.1", 8901), M.H)
t = threading.Thread(target=srv.serve_forever, daemon=True)
t.start()
time.sleep(0.5)
BASE = "http://127.0.0.1:8901"
os.chdir("/data/workspace")

def run(args, tag):
    print(f"\n{'='*8} {tag} {'='*8}")
    r = subprocess.run([sys.executable] + args, capture_output=True, text=True, timeout=120)
    print(r.stdout[-3000:])
    if r.returncode != 0:
        print("STDERR:", r.stderr[-1500:])
    return r.stdout

try:
    # 1. 建基线（代码自动探测+聚类+版本串扫描）
    run(["rk_baseline.py", BASE, "--auth", "/system/", "--delay", "0.3", "--out", "/tmp/base.json"], "S1 基线")
    print("\n--- baseline.json 摘要 ---")
    b = json.load(open("/tmp/base.json"))
    print("层:", list(b["layers"].keys()), "| 版本串:", b.get("versions"))

    # 2. 形态变体（代码自动生成，AI 不用手搓 URL）
    run(["rk_morph.py", "/examples/", "<APPROOT>/public/a", "--base", BASE, "--out", "/tmp/urls.txt"], "S2 形态变体")
    urls = [l for l in open("/tmp/urls.txt") if l.strip() and not l.startswith("#")]
    print(f"生成 {len(urls)} 条候选 URL（AI 零手搓）")

    # 3. 批量探测 + 自动分层
    run(["rk_probe.py", "-f", "/tmp/urls.txt", "--baseline", "/tmp/base.json",
         "--delay", "0.3", "--scan-version", "--ev", "/tmp/ev"], "S3 批量探测")

    # 4. GBK 源码提取
    gbk = '<html><meta charset="gbk"><script>var _webRootPath="<APPROOT>/";' \
          '$("#a").click(function(){location.href=_webRootPath+"public/<自述路径·校历>";});' \
          '</script><a id="b" href="<APPROOT>/<自述路径·运行环境指南>">运行环境指南</a></html>'
    open("/tmp/login.html", "wb").write(gbk.encode("gbk"))
    run(["rk_extract.py", "-f", "/tmp/login.html", "--urls-only"], "S4 源码提取(GBK)")

    # 5. CVE 版本比对（确定性交给代码）
    run(["rk_cve.py", "--init"], "S5a CVE模板")
    feed = {"version": "9.0.99", "product": "tomcat", "cves": [
        {"id": "CVE-2025-55752", "intro": "9.0.0.M11", "fixed": "9.0.109"},
        {"id": "CVE-2026-68763", "intro": "9.0.39", "fixed": "9.0.120"},
        {"id": "CVE-2025-55754", "intro": "9.0.40", "fixed": "9.0.109"},
    ]}
    json.dump(feed, open("/tmp/feed.json", "w"))
    run(["rk_cve.py", "--feed", "/tmp/feed.json"], "S5b CVE命中")

    # 6. 报告 + 措辞红线
    f = {"target": "mock", "findings": [
        {"state": "实锤", "level": "中危", "title": "Tomcat 9.0.99 未修复组件",
         "path": "/docs/", "evidence": ["404·<LEN-649> 页脚 Apache Tomcat/9.0.99"],
         "impact": "命中多个已知CVE", "repro": "GET /docs/", "fix": "升级9.0.122", "submit": True},
        {"state": "推断", "level": "中危", "title": "统计接口未授权",
         "path": "/clicktimes.jsp", "evidence": ["缺参200·0B 非912B"],
         "impact": "已确认无鉴权，攻击者可执行代码", "repro": "GET", "fix": "加鉴权",
         "submit": True, "caveat": "未实际触发"}]}
    json.dump(f, open("/tmp/f.json", "w"), ensure_ascii=False)
    run(["rk_report.py", "-f", "/tmp/f.json"], "S6 报告+红线检查")
finally:
    srv.shutdown()
print("\n[done]")
