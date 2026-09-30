#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run.py —— 确定性步骤编排器

设计原则：**凡是可判定的动作，一律不占用模型的注意力。**
模型只在脚本的产出上做「意义判断」——数据属不属于我、这个业务合理吗、
能不能串起来。

用法：
  python3 run.py p1 --host https://target.com --req req.txt --ids ids.txt
  python3 run.py daily --dir ./work          # 一条命令跑完当天全部确定性步骤
  python3 run.py ask p1                      # 打印该批次的引导提问（给模型看）
"""

import argparse
import os
import subprocess
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

# ==================== 引导提问（脚本跑完后，交给模型的部分） ====================
# 不是规则，是提问。规则替代思考，提问激活思考。

ASK = {
    "cal": """
先看「工作流缺口」那一段。

**那些定位不到任何步骤的漏洞，为什么我的工作流看不见它？**
是步骤缺失（压根没这类检测），还是信号缺词（有这个步骤但描述没覆盖）？
前者要加步骤，后者只要补几个信号词。

再看「各步骤命中贡献」。

**哪个步骤命中最多？哪个是 0？**
命中最多的是主产出方向，值得多分配时间。
命中 0 的，要么是不做的方向（那就删掉），要么是样本偏了（那就补样本）。
别留着既不产出又不删除的步骤——它只会稀释注意力。

最后，**这 15 个漏洞的根因，有多少是同一个？**
如果三个以上指向同一根因（比如都是「缺失鉴权」），
说明这是当前周期的高频根因——你的目标上大概率也有。
""",
    "p0": """
上一步脚本把目标的资产列出来了：子域、开放端口、技术栈、暴露的文档和备份。

现在问自己一件事：**这些人里，哪一个最值钱？**
判断标准不是"哪个看起来好打"，而是"哪个被打之后后果最严重"。
一个存放用户手机号的后台，价值远高于一个静态官网，哪怕后者更好打。

再问第二件：**哪些入口是别人不会去看的？**
主站页面上能点的功能，几百人已经测过了。
真正出货的是那些不在页面上、但确实在跑的东西——
老版本接口、内部路径、移动端专用的域名、几个月前下线的但没关掉的服务。

把这两个问题的答案写下来，就是这一轮要打的目标清单。
""",
    "p1": """
脚本告诉你：哪些请求在删掉凭证、或换成另一个账号的凭证之后，
依然返回了数据。

但在你认定它是漏洞之前，先想清楚一件事：
**这些数据，本来就该公开吗？**

一个商品列表返回全部商品，那叫正常功能。
一个订单详情返回了别人的手机号和收货地址，那才叫越权。
所以你要回答的不是"有没有返回数据"，而是"**返回的数据属不属于我**"。

确认属于别人之后，再问第二层：
如果这个接口真的没做校验，那么——
**同一批代码写的其他接口呢？管理端的同名接口呢？几个月前的老版本路径呢？**

这是最容易把低危拉成高危的地方：
一个接口越权只是低危，同一根因的一批接口越权就是高危。

最后问第三层，也是最容易被跳过的：
**如果这么明显的洞，为什么之前没人报？**
答案常常是"有 WAF"、"需要特定配置"、"根本没人测到这里"。
先想清楚这个，再决定投入多少时间。
""",
    "p2": """
脚本做的都是机械比对。它不知道什么叫"合理"。

所以这一轮，你要做的是**理解业务**。
打开目标，像一个真实用户那样把它从头到尾用一遍，然后问：

**这笔钱、这张券、这个库存，在服务端眼里到底是怎么算的？**
前端显示的价格不算数——服务端的计算逻辑才是真相。
如果下单请求里带着金额字段，那它多半是有问题的，
因为金额本该由服务端从商品表里算出来，而不是从请求里读。

**这里的"限制"是真的限制吗？**
"每人限领一张"这句话，是写在页面上的，还是写在服务端的？
如果是前者，那同时发二十个请求试试——单线程测必定正常，必须并发。

**这些步骤，能不能跳过？**
多步流程里，每一步的校验是独立的还是连续的？
直接请求最后一步，看后端认不认。

这三个问题，脚本一个都答不了。它们需要你理解这个业务在做什么。
""",
    "p3": """
这一轮的目标是：**别把别人的发现原样复述一遍，要从里面看出他没看出来的东西。**

拿到一篇公开报告，先别急着复现。问自己：

**他改的那个参数，为什么会生效？缺的是哪一道校验？**
这是根因。多数人只读到"改了什么"，照做一遍就交了。

**这个根因，还可能藏在哪些地方？**
同一个模块的其他接口、反方向的操作（能读就能改吗？）、
换了 HTTP 方法还灵吗、老版本路径呢、移动端接口呢。

**如果防护是黑名单，那它的等价写法有多少种？**
黑名单几乎总能绕。编码、大小写、路径分隔符替换、IP 进制、域名指回——
每一样都试。

**最后，也是最重要的：如果这么明显，为什么原作者停在这里？**
他很可能不是没想到，而是试过没成。
想清楚这个再动手，能省下半天。
""",
    "report": """
写报告之前，用三个问题过滤一遍：

**一个不了解这个目标的人，照着我的步骤能复现吗？**
不能，就回去补步骤。这是被打回最常见的原因。

**我写的是业务后果，还是技术名词？**
"存在越权漏洞"没有信息量。
"任意登录用户可遍历全站订单，包含手机号与收货地址，实测可拉取 N 条"
这才叫危害。

**修复建议落到代码层面了吗？**
"加强校验"不算建议。
"在 XxxService.getOrder 中增加 order.userId 与当前登录用户的比对"才算。

三个问题都答得上来，再提交。
""",
}


def run(cmd, desc=""):
    if desc:
        print(f"\n{'='*60}\n▶ {desc}\n{'='*60}")
    r = subprocess.run(cmd, shell=True, cwd=HERE)
    return r.returncode


def cmd_p1(a):
    """越权批：删凭证 + ID 替换，全部确定性动作"""
    out = a.out or os.path.join(a.dir, "p1_unauth.json")
    rc = 0
    if a.req:
        rc |= run(f"{PY} src_scout.py unauth --file {a.req} --out {out}", "A1 删凭证未授权")
    if a.req and a.ids and a.param:
        out2 = a.out or os.path.join(a.dir, "p1_idor.json")
        rc |= run(
            f"{PY} src_scout.py idor --file {a.req} --param {a.param} --ids {a.ids} "
            f"--cookie-a '{a.cookie_a or ''}' --cookie-b '{a.cookie_b or ''}' --out {out2}",
            "A2/A3 资源 ID 越权")
    print_ask("p1")
    return rc


def cmd_cal(a):
    """P0 第零步：收割近三月漏洞 → 反向校准工作流 → 外推"""
    if a.file:
        out = a.out or os.path.join(a.dir, "calib.json")
        run(f"{PY} src_calibrate.py load --file {a.file} --out {out}", "工作流反向校准")
        run(f"{PY} src_variant.py gen --file {a.file} --top 8", "模式泛化外推")
    else:
        out = a.out or os.path.join(a.dir, "calib.json")
        run(f"{PY} src_calibrate.py demo --out {out}", "工作流反向校准（内置样本）")
        run(f"{PY} src_variant.py demo --top 6", "模式泛化外推（内置样本）")
    print_ask("cal")
    return 0


def cmd_p0(a):
    """资产测绘：泄露路径探测"""
    if not a.host:
        print("需要 --host")
        return 1
    out = a.out or os.path.join(a.dir, "p0_leak.json")
    run(f"{PY} src_scout.py leak --url {a.host} --out {out}", "信息泄露路径探测")
    print_ask("p0")
    return 0


def cmd_daily(a):
    """一条命令跑完当天全部确定性步骤"""
    os.makedirs(a.dir, exist_ok=True)
    print(f"[*] 工作目录: {a.dir}")
    run(f"{PY} src_calibrate.py demo --out {a.dir}/calib.json", "P0 工作流反向校准")
    run(f"{PY} src_intel.py demo --top 10", "情报打分（内置样本）")
    run(f"{PY} src_variant.py demo --top 6", "模式泛化（内置样本）")
    if a.host:
        run(f"{PY} src_scout.py leak --url {a.host} --out {a.dir}/p0_leak.json", "泄露路径探测")
    print("\n[*] 确定性步骤完成。以下是需要你（模型）思考的部分：")
    for k in ("cal", "p0", "p1", "p2", "p3"):
        print_ask(k)
    return 0


def print_ask(key):
    t = ASK.get(key)
    if not t:
        return
    print("\n" + "─" * 60)
    print(f" 引导提问 · {key.upper()}")
    print("─" * 60)
    print(textwrap.dedent(t).strip())


def cmd_ask(a):
    keys = [a.key] if a.key != "all" else ["cal", "p0", "p1", "p2", "p3", "report"]
    for k in keys:
        print_ask(k)
    return 0


def main():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--dir", default="./work", help="工作目录")

    ap = argparse.ArgumentParser(description="确定性步骤编排器：脚本做判定，模型做意义")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("cal", parents=[common], help="P0 第零步：收割漏洞并反向校准工作流")
    s.add_argument("--file", help="近三月漏洞 JSON（无则跑内置样本）")
    s.add_argument("--out")
    s.set_defaults(func=cmd_cal)

    s = sub.add_parser("p0", parents=[common], help="资产测绘")
    s.add_argument("--host"); s.add_argument("--out")
    s.set_defaults(func=cmd_p0)

    s = sub.add_parser("p1", parents=[common], help="越权批")
    s.add_argument("--host"); s.add_argument("--req"); s.add_argument("--ids")
    s.add_argument("--param"); s.add_argument("--cookie-a"); s.add_argument("--cookie-b")
    s.add_argument("--out")
    s.set_defaults(func=cmd_p1)

    s = sub.add_parser("daily", parents=[common], help="跑完当天全部确定性步骤")
    s.add_argument("--host")
    s.set_defaults(func=cmd_daily)

    s = sub.add_parser("ask", parents=[common], help="打印引导提问")
    s.add_argument("key", nargs="?", default="all",
                   choices=["cal", "p0", "p1", "p2", "p3", "report", "all"])
    s.set_defaults(func=cmd_ask)

    a = ap.parse_args()
    sys.exit(a.func(a))


if __name__ == "__main__":
    main()
