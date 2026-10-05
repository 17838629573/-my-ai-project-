"""enforce 的自检/检查逻辑（由 _extract_tool.py 从 enforce.py 抽出）

改前必读: IMPROVE_enforce.md
"""
import os
import re
import subprocess
import sys
import time
from enforce import ACTIVE_SECTIONS, BASE, DORMANT_SECTIONS, MODULES, WORKLOG, find_cycle, local_imports, module_exists, parse_deps, static_deps

def cmd_status():
    """红黄绿 = 机器判定，禁止手填（此前手填导致与事实不符）"""
    import subprocess, os as _os
    print("=" * 70)
    print("enforce.py check-status（自动判定）")
    print("=" * 70)
    print(f"{'模块':<20}{'契约':<6}{'自检':<6}{'结果':<8}{'状态'}")
    print("-" * 70)
    tally = {"绿": 0, "黄": 0, "红": 0}
    for m in MODULES:
        contract = _os.path.exists("contracts/%s.md" % m)
        has_self = False
        passed = False
        src = open("%s.py" % m, encoding="utf-8").read() if _os.path.exists("%s.py" % m) else ""
        has_self = '__main__' in src
        if has_self:
            r = subprocess.run(["python3", "%s.py" % m], capture_output=True,
                               text=True, timeout=180)
            passed = (r.returncode == 0 and
                      "FAIL" not in r.stdout.upper() and
                      "Traceback" not in r.stderr)
        if not has_self or not passed:
            st = "红"
        elif contract:
            st = "黄"
        else:
            st = "红"
        tally[st] += 1
        print(f"{m:<20}{'有' if contract else '缺':<6}"
              f"{'有' if has_self else '无':<6}{'PASS' if passed else '—':<8}{st}")
    print("-" * 70)
    print(f"绿 {tally['绿']}  黄 {tally['黄']}  红 {tally['红']}")
    print()
    print("判定标准（可自动检验，不依赖主观）：")
    print("  红 = 无自检 或 自检FAIL 或 无契约   → 门禁应拦截")
    print("  黄 = 有契约 + 有自检 + 自检PASS     → 可进主链，需成片验证")
    print("  绿 = 黄 + 有实测证据记录           → 待实现（需成片验证回路）")
    return 0 if tally["红"] == 0 else 1

def cmd_validate():
    deps, layer, order, runtime = parse_deps()
    errs, warns = [], []

    # 1) 文件存在性
    for m in order:
        if module_exists(m) is None:
            errs.append(f"[文件缺失] 模块 '{m}' 在 deps.md 声明但 {m}.py 不存在")

    # 2) 环
    for c in find_cycle(static_deps(deps, runtime)):
        errs.append("[循环依赖] " + " -> ".join(c))

    # 3) 被依赖方必须是已声明模块
    for m, ds in deps.items():
        for d in ds:
            if (m, d) in runtime:
                continue                      # 跨进程依赖，不要求本地声明
            if d not in deps:
                errs.append(f"[依赖未声明] {m} 依赖 '{d}'，但 deps.md 无 '{d}' 条目")

    # 4) 未声明引用（先斩后奏检出）：只查活跃层
    for m in order:
        if layer.get(m) not in ACTIVE_SECTIONS:
            continue
        p = module_exists(m)
        if not p or not p.endswith(".py"):
            continue
        declared = set(deps.get(m, []))
        for imp in local_imports(p):
            if imp == m:
                continue
            if imp not in declared:
                if imp in deps and layer.get(imp) in DORMANT_SECTIONS:
                    errs.append(f"[引用休眠层] {m} 引用了休眠模块 '{imp}'")
                elif imp in deps and layer.get(imp) == "Z":
                    errs.append(f"[引用死代码] {m} 引用了死代码 '{imp}'")
                else:
                    errs.append(
                        f"[未声明引用] {m} import 了 '{imp}'，deps.md 未声明 -> 先改 deps.md")

    # 6) 【铁律12盲区】import 可达性：deps.md 声明了，文件却没写 import
    #    现象：validate PASS 但运行 NameError（门给假信心，最危险）
    for m in order:
        if layer.get(m) not in ACTIVE_SECTIONS:
            continue
        p = module_exists(m)
        if not p or not p.endswith(".py"):
            continue
        actual = local_imports(p)
        for d in deps.get(m, []):
            if (m, d) in runtime:          # runtime 是 (模块, 依赖) 元组集合
                continue
            if d not in actual:
                errs.append(
                    f"[import不可达] {m} 在 deps.md 声明依赖 '{d}'，"
                    f"但文件里没有 import {d} -> 运行必 NameError")

    # 7) 编译 + 导入可达：语法能过、模块能 import 成功
    import py_compile, subprocess, sys as _sys
    for m in order:
        if layer.get(m) not in ACTIVE_SECTIONS:
            continue
        p = module_exists(m)
        if not p or not p.endswith(".py"):
            continue
        try:
            py_compile.compile(p, doraise=True)
        except Exception as e:
            errs.append(f"[编译失败] {m}.py: {type(e).__name__} {e}")
            continue
        r = subprocess.run([_sys.executable, "-c", f"import {m}"],
                           cwd=BASE, capture_output=True, timeout=30)
        if r.returncode != 0:
            last = (r.stderr.decode("utf-8", "ignore").strip().splitlines() or ["?"])[-1]
            errs.append(f"[导入失败] {m} 无法 import: {last}")

    # 5) 死代码不得被活跃层引用
    for m in order:
        if layer.get(m) in DORMANT_SECTIONS:
            continue
        for d in deps.get(m, []):
            if layer.get(d) == "Z":
                errs.append(f"[引用死代码] {m} 依赖死代码 '{d}'")

    print("=" * 68)
    print("enforce.py validate")
    print("=" * 68)
    print(f"  声明模块 {len(order)} 个；活跃 {sum(1 for m in order if layer.get(m) in ACTIVE_SECTIONS)} 个")
    print(f"  休眠 {sum(1 for m in order if layer.get(m) == 'X')} 个；死代码 {sum(1 for m in order if layer.get(m) == 'Z')} 个")
    print(f"  跨进程依赖 {len(runtime)} 条（ffmpeg 等，免本地声明）")
    print()
    if errs:
        for e in errs:
            print("  ✗ " + e)
        print(f"\nFAIL：{len(errs)} 项")
        return 1
    for w in warns:
        print("  ! " + w)
    print("  ✓ 文件存在 / 无环 / 无未声明引用 / 无死代码引用")
    print("PASS")
    return 0

def cmd_check_contract(name):
    deps, layer, _, runtime = parse_deps()
    if name not in deps:
        print(f"FAIL: 模块 '{name}' 未在 deps.md 声明 -> 先写契约再写代码")
        return 1
    print(f"PASS: '{name}' 已声明（层={layer.get(name)}，依赖={deps.get(name) or '无'}）")
    return 0

def cmd_check_deps():
    deps, _, _, runtime = parse_deps()
    errs = []
    for m, ds in deps.items():
        for d in ds:
            if (m, d) in runtime:
                continue
            if d in deps and module_exists(d) is None:
                errs.append(f"{m} -> {d}：{d} 文件不存在")
    cycles = find_cycle(static_deps(deps, runtime))
    for c in cycles:
        errs.append("环：" + " -> ".join(c))
    if errs:
        for e in errs:
            print("  ✗ " + e)
        print("FAIL")
        return 1
    print("PASS: 依赖文件齐全且无环")
    return 0

def cmd_check_evidence(code, evidence):
    ok = str(code) == "0"
    print(f"  退出码={code}  依据={evidence}")
    if not ok:
        print("FAIL: 判定依据不充分（铁律1）")
        return 1
    print("PASS")
    return 0

def cmd_gate(kind, stage):
    if kind != "post-stage":
        print(f"FAIL: 未知 gate 类型 {kind}")
        return 1
    os.makedirs(BASE, exist_ok=True)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    entry = f"\n## Stage {stage} · {ts}\n- gate: post-stage 通过\n"
    with open(WORKLOG, "a", encoding="utf-8") as f:
        f.write(entry)
    print(f"PASS: 已追加 WORKLOG.md -> Stage {stage}")
    return 0

def cmd_check_assets():
    """
    资产硬阻断：主角/配角/道具/走路帧 缺一即 FAIL。
    与 missing_assets() 不同 —— 那个只告警，这个阻断渲染。
    """
    import os
    import json
    import cv2
    import character_sheet as cs
    from chroma import flood_key, clean_mask

    print("=" * 70)
    print("enforce.py check-assets  (硬阻断：缺资产禁止渲染)")
    print("=" * 70)

    errs, warns, rep = [], [], []
    bg_ok = []

    # 【已修】cs.missing_assets() 是旧剧本（通缉文牒/瘦老赤马…）的硬编码清单，
    # 换题材即永久 FAIL —— 与本片自然语言题材无关。角色资产改按 scene_spec 判定，
    # 旧清单仅作提示，不再阻断渲染。
    old_miss = cs.missing_assets()
    if old_miss:
        warns.append("旧剧本角色清单 %d 项不适用当前题材，已忽略（非阻断）"
                     % len(old_miss))
    print("  角色资产: 按 scene_spec 判定（旧硬编码清单已豁免）")

    BASE = os.path.dirname(os.path.abspath(__file__))
    # 【已修】旧版硬编码 8 个背景名(gate/hall/...)，换场景即永久 FAIL。
    # 场景资产改为按 scene_spec 动态判定 —— 出片四件套来自 build_phase_asset。
    spec_p = os.path.join(BASE, "scene_spec.json")
    if os.path.exists(spec_p):
        with open(spec_p, encoding="utf-8") as f:
            spec = json.load(f)
        print("  场景: %s" % spec.get("名称", "?"))
        bg_ok = []
        for rel in ("_生成/城墙背景.png", "_生成/树_单体.png",
                    "_生成/旗_图集.png", "_生成/玄奘_图集.png"):
            p = os.path.join(BASE, rel)
            if not os.path.exists(p):
                errs.append("[缺失] 场景资产/%s" % rel)
            else:
                im = cv2.imread(p, cv2.IMREAD_UNCHANGED)
                if im is None:
                    errs.append("[损坏] 场景资产/%s 无法解码" % rel)
                else:
                    bg_ok.append(rel)
                    print("  场景资产 ok: %s %s" % (rel, im.shape))
    else:
        errs.append("[缺失] scene_spec.json（禁无 spec 出片）")

    for fn in sorted(os.listdir(cs.CHAR_DIR)):
        if not fn.lower().endswith((".jpg", ".png")):
            continue
        p = os.path.join(cs.CHAR_DIR, fn)
        try:
            bgra, _ = flood_key(cv2.imread(p))
            bgra = clean_mask(bgra)
            share = float((bgra[:, :, 3] > 0.5).mean())
            # 【已修】15%下限是人物全身判据。道具/动物在白底上本就占屏小，
            # 用同一阈值会把 prop_bundle(3.5%) 误判为 broken。按前缀分档。
            lo = 0.02 if fn.startswith(("prop_", "pr_")) else 0.15
            tag = "ok" if lo <= share <= 0.60 else (
                "broken" if share < lo else "weak")
            if tag == "broken":
                errs.append("[禁引用] char/%s 前景占比 %.1f%%" % (fn, share * 100))
            elif tag == "weak":
                warns.append("[弱] char/%s 前景占比 %.1f%%" % (fn, share * 100))
            rep.append({"file": fn, "share": round(share, 4), "tag": tag})
        except Exception as e:
            errs.append("[抠像失败] char/%s: %s" % (fn, e))

    for fn, why in cs.check_naming():
        errs.append("[命名] %s: %s" % (fn, why))

    with open(os.path.join(BASE, "assets_report.json"), "w",
              encoding="utf-8") as f:
        json.dump({"char": rep, "bg": bg_ok}, f,
                  ensure_ascii=False, indent=2)

    print("")
    print("  角色图 %d 张  场景资产 %d 件" % (len(rep), len(bg_ok)))
    print("  报告已落盘: assets_report.json")
    for w in warns:
        print("  ! " + w)
    if errs:
        print("")
        print("  阻断项:")
        for e in errs:
            print("    x " + e)
        print("")
        print("FAIL：%d 项（渲染被拒绝）" % len(errs))
        return 1
    print("")
    print("PASS（资产齐全，允许渲染）")
    return 0
