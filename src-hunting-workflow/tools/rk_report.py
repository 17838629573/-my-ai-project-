#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rk_report.py —— 三态清单 + 措辞红线检查

两个作用：
1. 把 findings.json 渲成可提交的 markdown（复现路径/证据/定级/修复建议）
2. **自动拦截会毁掉报告的措辞** —— 本项目反复强调的红线，代码化后不会再犯

用法:
  python3 rk_report.py -f findings.json -o report.md
  python3 rk_report.py --init          # 生成 findings 模板
"""

import argparse, json, re, sys

# 措辞红线：左边是"会被引爆/打回"的写法，右边是正确写法
RED_LINES = [
    (r"已确认无鉴权|确认无鉴权|已验证无鉴权", "未观察到鉴权拦截（0B≠无鉴权的证明）"),
    (r"可写入任意数据|任意写入", "可篡改该接口对应业务数据（参数均为数字型，无自由输入）"),
    (r"可执行代码|代码执行|RCE|getshell", "（天花板是数据完整性，非代码执行；除非源码证实）"),
    (r"已验证存在(?!.*未触发)", "依据源码/同族端点推断，未实际触发"),
    (r"可读取任意文件|任意文件读取", "（未实际读取，勿写）"),
    (r"Spring WebFlow", "（未证实该产品使用 Spring WebFlow，改用'异常响应泄露技术栈'）"),
    (r"文件存在性枚举漏洞|响应差异漏洞", "（状态可区分是方法论不是漏洞；写'错误信息与状态过度暴露'）"),
]

TEMPLATE = {
    "target": "目标域名",
    "findings": [
        {
            "state": "实锤",           # 实锤 / 推断 / 排除
            "level": "中危",           # 高危/中危/低危/无
            "title": "一句话标题",
            "path": "复现 URL 或路径",
            "evidence": ["证据1（含 md5/长度/响应原文）"],
            "impact": "危害描述",
            "repro": "复现步骤",
            "fix": "修复建议",
            "submit": True,
            "caveat": "限定条件/风险（如 未实际触发声明）"
        }
    ]
}


def check_text(t):
    warns = []
    for pat, right in RED_LINES:
        for m in re.finditer(pat, t or ""):
            warns.append((m.group(0), right))
    return warns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-f", "--file")
    ap.add_argument("-o", "--out")
    ap.add_argument("--init", action="store_true")
    a = ap.parse_args()

    if a.init:
        print(json.dumps(TEMPLATE, ensure_ascii=False, indent=2))
        return
    if not a.file:
        ap.error("给 -f 或 --init")

    data = json.load(open(a.file, encoding="utf-8"))
    fs = data.get("findings", [])
    by = {"实锤": [], "推断": [], "排除": []}
    for x in fs:
        by.setdefault(x.get("state", "推断"), []).append(x)

    L = []
    L.append(f"# {data.get('target','目标')} 漏洞清单（三态）\n")
    L.append(f"- 实锤 {len(by['实锤'])} · 推断 {len(by['推断'])} · 排除 {len(by['排除'])}\n")
    L.append("> 三态定义：**实锤**=有真实响应证据可复现；**推断**=依据源码/同族端点外推，未触发；"
             "**排除**=已实测否定，不再投入。\n")

    for st in ("实锤", "推断", "排除"):
        if not by[st]:
            continue
        L.append(f"\n## {st}\n")
        for x in by[st]:
            L.append(f"\n### [{x.get('level','?')}] {x.get('title','')}\n")
            L.append(f"- **路径**：`{x.get('path','')}`")
            if x.get("evidence"):
                L.append("- **证据**：")
                for e in x["evidence"]:
                    L.append(f"  - {e}")
            if x.get("impact"):
                L.append(f"- **危害**：{x['impact']}")
            if x.get("repro"):
                L.append(f"- **复现**：{x['repro']}")
            if x.get("caveat"):
                L.append(f"- **限定**：{x['caveat']}")
            if x.get("fix"):
                L.append(f"- **修复**：{x['fix']}")
            L.append(f"- **提交**：{'是' if x.get('submit') else '否'}")

    # 红线检查
    L.append("\n\n## 措辞红线检查\n")
    blob = json.dumps(data, ensure_ascii=False)
    warns = check_text(blob)
    if not warns:
        L.append("未触发红线。\n")
    else:
        L.append("以下问题会在审核时被追问，必须改：\n")
        seen = set()
        for bad, right in warns:
            if bad in seen:
                continue
            seen.add(bad)
            L.append(f"- 写了「{bad}」→ 应改为：{right}")

    out = "\n".join(L)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(out)
        print(f"[+] 写入 {a.out}")
        if warns:
            print(f"[!] 触发 {len(set(w[0] for w in warns))} 处措辞红线，已列在报告末尾")
    else:
        print(out)


if __name__ == "__main__":
    main()
