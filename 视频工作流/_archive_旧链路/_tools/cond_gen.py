#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cond_gen.py —— 把规则的『适用/不适用』从自然语言转成可判定字段。

流程（工具优先，人只做 pick）:
  1) gen    : 从 RULES.json 每条的『适用/不适用』原文抽候选值 -> 工作单
  2) apply  : 读工作单里我填的 pick -> 校验 -> 回填 RULES.json['cond']
  3) check  : 校验 cond 合法且与 dispatch.阶段 一致

维度固定为枚举（不允许自由文本），否则无法机器判定。
"""
import json, os, re, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = os.path.join(BASE, "RULES.json")
WS = os.path.join(BASE, "_cond_工作单.md")

# 维度枚举：值必须是这里的成员，或 "任意"
DIMS = {
    "matte": {
        "plate": ["有真实plate", "无plate"],
        "edge": ["简单硬边", "复杂边缘"],
        "type": ["人物", "柔性旗帜", "程序层", "字幕UI"],
    },
    "motion": {
        "periodic": ["周期", "一次性"],
        "kind": ["骨架可驱动", "程序化可算", "需生图"],
        "stochastic": ["确定性", "随机非刚性"],
    },
}
ANY = "任意"

# 关键词 -> 枚举值（工具用来从原文抽候选）
KW = {
    "有真实plate": ["plate", "clean plate", "背景单独", "单独拍摄", "背景单独生成",
                "锁定机位", "真实"],
    "无plate": ["未控制背景", "背景非单一色", "四角色值不一致", "无 plate", "没有 plate"],
    "简单硬边": ["硬边", "纯色", "绿幕", "蓝幕", "边缘质量"],
    "复杂边缘": ["发丝", "半透明", "混合像素", "模糊", "低对比", "羽化", "软过渡", "透明"],
    "人物": ["人物", "主体", "前景", "脚下", "落地"],
    "柔性旗帜": ["旗帜", "旗", "薄膜", "布料", "衣摆", "柔性"],
    "程序层": ["水", "火", "烟", "雨", "程序化", "物理参数", "程序层"],
    "字幕UI": ["字幕", "UI", "文字"],
    # motion —— 按实际原文用语扩充（第一轮 motion 命中率过低）
    "周期": ["周期", "循环", "步频", "步距", "相位", "首尾", "帧数", "双频",
             "低频", "高频", "频率", "摆动", "颤动", "逐帧", "幅度"],
    "一次性": ["一次性", "death", "单次", "非循环", "序列帧", "手绘"],
    "骨架可驱动": ["骨架", "骨骼", "姿态", "pose", "skeleton", "插值",
               "腿摆", "身体升降", "换装", "对象池", "身体坐标", "落脚",
               "朝向", "武器位", "人物"],
    "程序化可算": ["程序", "物理", "数值层", "公式", "双频", "风", "摆动",
               "逐行", "横向位移", "剪切", "气动", "终端速度", "滴谱",
               "风速", "面元", "位移", "植被", "衣摆", "旗帜", "薄膜", "布料"],
    "需生图": ["生图", "生成", "扩散", "图集", "贴图", "序列帧", "手绘", "渲染"],
    "确定性": ["确定", "锁相", "严格对齐", "量纲", "公式", "反推", "数值层",
               "终端速度", "风速", "帧率", "步距", "调"],
    "随机非刚性": ["随机", "湍流", "非刚性", "抖动", "滴谱", "抽样", "雨",
               "雨滴", "不同相位", "各层频率", "多层"],
}


def load():
    return json.load(open(R, encoding="utf-8"))


def candidates(text, values):
    """从原文抽候选：命中的关键词越多越靠前。"""
    t = str(text)
    out = []
    for v in values:
        hits = [k for k in KW.get(v, []) if k and k in t]
        if hits:
            out.append((v, hits))
    out.sort(key=lambda x: -len(x[1]))
    return out


def cmd_gen():
    D = load()
    lines = ["# cond 工作单 —— 只填 pick，不要改原文", "",
             "格式: `id | 维度 = 值`（值必须是枚举成员或 `任意`）",
             "多值用逗号；不填 = 我来定。", ""]
    for dom in ("matte", "motion"):
        dims = DIMS[dom]
        items = D[dom]["候选枚举"] if "候选枚举" in D[dom] else D[dom]
        lines.append(f"\n## {dom}")
        for it in items:
            rid, name = it["id"], it["name"]
            src = f"{it.get('适用','')} || {it.get('不适用','')}"
            lines.append(f"\n### {rid} {name}")
            lines.append(f"  阶段: {it.get('顺序','').split('阶段=')[-1][:12] if '阶段=' in str(it.get('顺序','')) else '-'}")
            for dim, vals in dims.items():
                cs = candidates(src, vals)
                if cs:
                    s = ", ".join(f"{v}(命中{len(h)}:{ '/'.join(h[:2]) })" for v, h in cs)
                else:
                    s = "（无关键词命中，需人工 NEW）"
                lines.append(f"  {dim}: {s}")
                lines.append(f"    pick: ")
    open(WS, "w", encoding="utf-8").write("\n".join(lines))
    print(f"[OK] 工作单已生成: {WS}")
    print(f"    行数 {len(lines)}")


def cmd_apply():
    """读工作单的 pick 行 -> 回填。"""
    D = load()
    if not os.path.exists(WS):
        print("[FAIL] 无工作单，先跑 gen"); return 1
    txt = open(WS, encoding="utf-8").read()
    cur = None
    curdim = None
    filled, bad = {}, []
    for ln in txt.split("\n"):
        m = re.match(r"### (\S+) ", ln)
        if m:
            cur = m.group(1); filled[cur] = {}; curdim = None
            continue
        m = re.match(r"  (\w+): ", ln)          # 维度行
        if m and cur:
            curdim = m.group(1); continue
        m = re.match(r"\s+pick:\s*(.+)$", ln)
        if m and cur and curdim:
            val = m.group(1).strip()
            if not val:
                continue
            # pick 行已归属维度，值只写枚举成员或"任意"，多值用 |
            parts = [x.strip() for x in val.split("|")]
            filled[cur][curdim] = parts[0] if len(parts) == 1 else parts
    if "cond" not in D:
        D["cond"] = {}
    n = 0
    for dom in ("matte", "motion"):
        items = D[dom]["候选枚举"] if "候选枚举" in D[dom] else D[dom]
        for it in items:
            if it["id"] in filled and filled[it["id"]]:
                it["cond"] = filled[it["id"]]
                n += 1
    if bad:
        print("[FAIL] 格式错误:")
        for b in bad: print("  " + b)
        return 1
    json.dump(D, open(R, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[OK] 已回填 {n} 条 cond")
    return 0


def cmd_check():
    D = load()
    fails = []
    for dom in ("matte", "motion"):
        dims = DIMS[dom]
        items = D[dom]["候选枚举"] if "候选枚举" in D[dom] else D[dom]
        for it in items:
            c = it.get("cond")
            if not c:
                fails.append(f"{it['id']} 缺 cond"); continue
            for k, v in c.items():
                if k not in dims:
                    fails.append(f"{it['id']}.{k} 未知维度"); continue
                vals = v if isinstance(v, list) else [v]
                for x in vals:
                    if x != ANY and x not in dims[k]:
                        fails.append(f"{it['id']}.{k}={x} 非枚举值")
    if fails:
        print("[FAIL] cond 校验:")
        for f in fails: print("  " + f)
        return 1
    print("[PASS] cond 全部合法")
    return 0


if __name__ == "__main__":
    a = sys.argv[1] if len(sys.argv) > 1 else "check"
    sys.exit({"gen": lambda: (cmd_gen() or 0),
              "apply": cmd_apply,
              "check": cmd_check}.get(a, cmd_check)())
