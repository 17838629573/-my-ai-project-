# 契约: proc/tools/refcheck
#   一句话: 核验收工判据/文档里引用的 arXiv 与 DOI 是否真实存在、标题是否与判据语义相关，抓"贴牌引用"
#   完整契约见 tools/__init__.py
#   依据: citesentry(PyPI) —— 检查引用存在性、URL 活跃度、内容相关性三件事；
#         academic-refchecker / RefChecker —— 用 arXiv / DOI / Semantic Scholar 多源核验；
#         CASRAI《Citation checking tools》—— "没有单一工具完全可靠，应多源交叉并披露不确定
#         性"，故本工具对无法联网核验的条目明确标 UNVERIFIED，绝不冒充已核实。
# -*- coding: utf-8 -*-
"""出处核验（R21）。

为什么需要它：
  harness.py 曾用 arXiv:2604.28025（ResiHMR）给"渲染剪影 vs 掩膜 IoU"判据背书。
  该论文真实存在（CVPR 2026），但主题是"残肢人群单图 3D 人体网格恢复"，与判据毫无方法论
  关系——用真实编号装饰无关判据，比凭空捏造更难发现，因为"编号是真的"。

机制：
  1. 从 _proc 下的 py/md 抽取 arXiv ID 与 DOI
  2. 联网取真实标题（arXiv API / Crossref API，两者均免费无需 key）
  3. 真实标题 与 引用所在行的判据描述 做实词集合 Jaccard 相似度
  4. 相似度过低 -> 报"疑似贴牌"；取不到 -> 标 UNVERIFIED（不算通过，也不算失败）

重要：UNVERIFIED 与 PASS 必须分开显示。网络不通时不能报"全部通过"。
"""
import html
import io
import json
import os
import re
import sys
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROC = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_PROC)

sys.path.insert(0, _PROC)

_ARXIV_RE = re.compile(r"[Aa]rXiv:\s*(\d{4}\.\d{4,5})")
_DOI_RE = re.compile(r"(?:doi\.org/|DOI:\s*)(10\.\d{4,9}/[^\s\"'）)]+)")
_CACHE = os.path.join(_HERE, ".refcache.json")
# 语义覆盖下限：低于此值判"编号真、论据不成立"。
# 0.30 = 期望语义词中至少三成出现在文献标题+摘要里。
_COVER_MIN = 0.30

# 实词停用：这些词在标题里出现不代表语义相关
_STOP = set("""a an the of and for with on in to from by is are we our using via based
towards toward novel deep learning neural network networks approach method methods
single image images video videos 3d 2d human body pose estimation""".split())

# 完整浏览器 UA：实测 export.arxiv.org 与部分站点对自定义短 UA 返回 403,
# 改用常见浏览器 UA 后 arxiv.org/abs/<id> 可正常抓取(实测 41KB 响应)。
UA = {"User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")}


def _words(s):
    return set(w for w in re.findall(r"[a-z]{3,}", (s or "").lower()) if w not in _STOP)


def _jaccard(a, b):
    A, B = _words(a), _words(b)
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def _coverage(expect, doc):
    """期望语义词被文献文本覆盖的比例（recall）。

    为何不用 Jaccard：文献文本(尤其摘要)词量远大于判据描述, 并集被稀释,
    Jaccard 天然偏低, 会把真相关的文献误判成贴牌。判"相关与否"要问的是
    "文献是否涵盖了判据的核心概念", 这正是 recall 的定义。
    """
    A, B = _words(expect), _words(doc)
    if not A:
        return 0.0
    return len(A & B) / len(A)


def _load_cache():
    try:
        with io.open(_CACHE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(c):
    try:
        with io.open(_CACHE, "w", encoding="utf-8") as f:
            json.dump(c, f, ensure_ascii=False, indent=1)
    except Exception as e:
        # 缓存写失败不致命（下次会重新联网），但不能静默吞掉——否则工具挂了外面看着像"没问题"
        sys.stderr.write("[refcheck] 缓存写入失败，本次结果不落盘：%s: %s\n"
                         % (type(e).__name__, e))


def _fetch_arxiv(aid, cache):
    """抓 arXiv 论文标题。

    端点选择有实测依据: export.arxiv.org 的 API 端点对本工具(即便带 UA)稳定返回
    HTTP 403 Forbidden; 而 arxiv.org/abs/<id> 页面可正常访问。故改走页面, 并从
    <meta name="citation_title"> 提取——该 meta 比 <title> 干净, 不含站点名后缀,
    且这是 arXiv 官方为引用工具显式提供的字段(arXiv 的 citation_* meta 约定)。
    """
    if aid in cache:
        return cache[aid]
    url = "https://arxiv.org/abs/%s" % aid
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=20) as r:
            txt = r.read().decode("utf-8", "replace")
        m = re.search(r'<meta name="citation_title" content="(.*?)"', txt, re.S)
        if m is None:  # 回退: 老页面或无该 meta 时取 <title>
            m = re.search(r"<title>(.*?)</title>", txt, re.S)
        title = None
        if m:
            title = re.sub(r"\s+", " ", html.unescape(m.group(1))).strip()
        # 摘要必需：仅凭标题判定会误杀。实测 ReinDiffuse 正文以 Floating 为四大
        # 物理违规之一, 但标题 "Crafting Physically Plausible Motions..." 里没有
        # floating 一词, 标题级 Jaccard=0.00 被误判为贴牌。故正文语义改用摘要。
        ma = re.search(r'<meta name="citation_abstract" content="(.*?)"', txt, re.S)
        abstract = re.sub(r"\s+", " ", html.unescape(ma.group(1))).strip() if ma else ""
        res = {"ok": title is not None, "title": title, "abstract": abstract,
               "src": "arXiv abs"}
    except Exception as e:
        res = {"ok": False, "title": None, "err": "%s" % e, "src": "arXiv abs"}
    cache[aid] = res
    return res


_PDF_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".refcache")


def _fetch_pdf_text(aid, cache):
    """抓 arXiv PDF 正文用于语义核验（仅当标题+摘要覆盖不足时才调用）。

    存在理由：部分判据的阈值出自论文"正文"(如 ReinDiffuse §Evaluation Metrics 的
    5cm 浮动/剪脚阈值)，而 arXiv 摘要页只讲方法不讲评测指标细节，仅凭
    title+abstract 判定会把"正确引用"误杀为贴牌(实测 coverage=0.00)。
    故做两级核验：先摘要，不足再取正文。结果落盘缓存，避免重复下 2MB+ PDF。
    """
    key = "pdf:" + aid
    if key in cache:
        return cache[key]
    text = ""
    try:
        os.makedirs(_PDF_CACHE, exist_ok=True)
        fp = os.path.join(_PDF_CACHE, re.sub(r"[^0-9a-zA-Z.]", "_", aid) + ".txt")
        if os.path.exists(fp):
            text = io.open(fp, encoding="utf-8", errors="replace").read()
        else:
            url = "https://arxiv.org/pdf/%s" % aid
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
            tmp = fp + ".pdf"
            with open(tmp, "wb") as f:
                f.write(raw)
            import subprocess
            out = subprocess.run(["pdftotext", tmp, fp], capture_output=True)
            if out.returncode == 0 and os.path.exists(fp):
                text = io.open(fp, encoding="utf-8", errors="replace").read()
            if os.path.exists(tmp):
                os.remove(tmp)
    except Exception:
        text = ""
    cache[key] = text
    return text


def _fetch_doi(doi, cache):
    if doi in cache:
        return cache[doi]
    url = "https://api.crossref.org/works/%s" % doi
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=15) as r:
            j = json.loads(r.read().decode("utf-8", "replace"))
        t = j.get("message", {}).get("title") or []
        res = {"ok": bool(t), "title": t[0] if t else None, "src": "Crossref API"}
    except Exception as e:
        res = {"ok": False, "title": None, "err": "%s" % e, "src": "Crossref API"}
    cache[doi] = res
    return res


def _is_self(path):
    """是否为本工具自身文件。

    跳过理由: self_check() 内含编造的假编号作为测试夹具
    (如 arXiv:1234.5678)，它们不是项目真实引用，扫进来会永远
    UNVERIFIED 并污染报告，让人误以为项目有可疑引用。
    """
    return os.path.abspath(path) == os.path.abspath(__file__)


def _iter_files():
    """遍历 _PROC 下所有待扫描的 .py/.md 文件（跳过缓存目录与本工具自身）。"""
    for dp, dn, fn in os.walk(_PROC):
        dn[:] = [d for d in dn if d not in ("__pycache__", ".git")]
        for f in fn:
            if not f.endswith((".py", ".md")):
                continue
            path = os.path.join(dp, f)
            if _is_self(path):
                continue
            yield path


def _read_lines(path):
    try:
        return io.open(path, encoding="utf-8").read().splitlines()
    except Exception:
        return []


def _refs_of_line(path, i, ln):
    out = []
    for m in _ARXIV_RE.finditer(ln):
        out.append((path, i, "arXiv", m.group(1), ln))
    for m in _DOI_RE.finditer(ln):
        out.append((path, i, "DOI", m.group(1).rstrip(".,;"), ln))
    return out


# 撤除标记：出现这些词的行，是在记录"我们撤掉了这个引用"，不是在引它。
# 历史误报：harness.py 的 mask_iou 注释写着"撤除说明：原引 ResiHMR(arXiv:2604.28025)
# …已撤除"，编号被误扫成待核验引用，且永远核不掉，看着像项目有可疑引用。
_RETRACT = ("撤除", "已移除", "已删除", "已撤回", "removed", "retracted")


def _is_retraction(ln):
    return any(w in ln for w in _RETRACT)


def _scan_files():
    """扫描全部引用，返回 (refs, skipped)。

    skipped 记录"撤除说明"里被引到的编号——它们不是真引用，但也不能静默丢弃，
    否则日后有人把已撤除的引用改回正式引用时工具会漏报。
    """
    out, skipped = [], []
    for path in _iter_files():
        for i, ln in enumerate(_read_lines(path), 1):
            if _is_retraction(ln):
                skipped.append("%s:%d（撤除说明，非引用）" % (
                    os.path.relpath(path, _ROOT), i))
                continue
            out.extend(_refs_of_line(path, i, ln))
    return out, skipped



# 判据名 -> 期望语义关键词（用于判"贴牌"）：只登记有明确语义的判据
# 覆盖度要求：下表必须与 harness.py 判据表一一对应。
# 历史 bug：只登记了 9/24 个判据（缺 float_m / feet_clip_m / skate_cm_frame 等），
# 未登记的判据其引用会被 _criterion_of 判为 None 而跳过语义比对，直接报 OK——
# 贴牌检测大面积空转却显示全绿。新增判据时必须同步登记，否则工具应报错（见 _SEM_COVER）。
_SEM = {
    "penetration_m": "penetration depth estimation rigid body collision GJK EPA slop overlap separation contact",
    "seg_penetration_m": "penetration depth estimation rigid body collision GJK EPA slop overlap separation contact",
    "contact_float_m": "penetration depth estimation rigid body collision GJK EPA slop overlap contact separation",
    "ground_penetration_m": "penetration depth estimation rigid body collision GJK EPA slop ground contact",
    "jitter_px": "jitter temporal stability smoothness frame difference pixel video quality",
    "pos_drift_m": "drift long horizon phase alignment world model video prediction cycle consistency",
    "mask_iou": "mask silhouette segmentation IoU rendered body shape overlap",
    "peak_rate_dps": "turn rotation angular velocity pelvis peak biomechanics degrees per second",
    "momentum_err": "momentum conservation impulse collision restitution rigid body dynamics",
    "arm_reach": "arm reach distance joint limit kinematic chain length target",
    "box_rest_m": "box release rest placement contact table surface detachment owner",
    "elbow_reflex": "elbow joint limit hyperextension reflex anatomical constraint avoid",
    "energy_gain": "energy gain conservation physics simulation bounce restitution damping",
    "feet_clip_m": "foot clipping interpenetration both feet distance ground contact",
    "flight_apex_err": "projectile flight apex trajectory ballistic parabola error height",
    "flight_g_err": "projectile gravity acceleration trajectory ballistic error fall",
    "float_m": "floating airborne foot contact ground clearance height skating",
    "frame_jump_ratio": "frame jump temporal discontinuity pose change ratio smoothness",
    "lower_pollution": "lower body pollution mask additive blend spine isolation layered",
    "mileage_rel_err": "mileage accumulated drift long horizon relative error integration",
    "restitution_err": "restitution coefficient bounce collision impulse error energy",
    "silhouette_gap_px": "silhouette gap mask continuity pixel rendered body segmentation",
    "silhouette_span_ratio": "silhouette span ratio mask rendered body proportion scale",
    "skate_cm_frame": "foot skating slide ground contact velocity displacement marker",
}


def _sem_cover():
    """判据名覆盖度：harness.py 判据表的每个判据都必须登记进 _SEM。

    单独成项是因为这是本工具的自我防卫：未登记的判据其引用会被
    _criterion_of 判为 None 而跳过语义比对，结果直接计入 verified 并报 OK——
    外表全绿，实际什么都没比对。新增判据忘记登记必须由工具抓，不能靠自觉。
    """
    hp = os.path.join(_PROC, "tests", "harness.py")
    if not os.path.exists(hp):
        return ["[R21 探针失效] 未找到 tests/harness.py，无法核对判据覆盖度"]
    txt = io.open(hp, encoding="utf-8").read()
    names = set(re.findall(r'^\s*"([a-z_]+)"\s*:\s*\(', txt, re.M))
    miss = sorted(n for n in names if n not in _SEM)
    if miss:
        return ["[R21 语义词典缺项] 判据 %s 未登记进 _SEM —— 其引用将跳过语义比对而误报 OK"
                % "、".join(miss)]
    return []


def _criterion_of(line):
    for k in _SEM:
        if k in line:
            return k
    return None


def _semantic_score(kind, rid, expect, title, abstract, cache):
    """判据语义 vs 文献文本的覆盖率，返回 (sim, 备注)。

    两级核验：先标题+摘要；不足则降级取 arXiv PDF 正文。
    存在理由：判据阈值常出自论文"正文 §Metrics"(如 ReinDiffuse 的 5cm 浮动阈值)，
    而摘要只讲方法不讲评测指标，仅凭摘要会把正确引用误杀(实测 0.00)。
    """
    if not expect:
        return None, ""
    doc = title + " " + abstract
    sim = _coverage(expect, doc)
    if sim >= _COVER_MIN or kind != "arXiv":
        return sim, ""
    ft = _fetch_pdf_text(rid, cache)
    if not ft:
        return sim, ""
    sim2 = _coverage(expect, ft)
    if sim2 <= sim:
        return sim, ""
    return sim2, "（正文核验 %.2f→%.2f）" % (sim, sim2)


def _check_ref(rel, ln, kind, rid, line, cache):
    """核验单条引用，返回 (状态, 文本, issue)。状态∈{verified, unchecked}。"""
    r = (_fetch_arxiv if kind == "arXiv" else _fetch_doi)(rid, cache)
    if r is None or not r.get("ok"):
        return "unchecked", "%s:%d %s:%s（未能核验%s）" % (
            rel, ln, kind, rid,
            "" if r is None else "：" + str(r.get("err", "无标题"))), None
    title = r["title"]
    crit = _criterion_of(line)
    sim, src_note = _semantic_score(kind, rid, _SEM.get(crit, ""), title,
                                    r.get("abstract", ""), cache)
    text = "%s:%d %s:%s -> 《%s》%s" % (
        rel, ln, kind, rid, title[:70],
        "" if sim is None else " 语义覆盖 %.2f%s" % (sim, src_note))
    iss = None
    if sim is not None and sim < _COVER_MIN:
        iss = ("[R21 疑似贴牌] %s:%d 判据 %s 引 %s:%s，但其《%s》与判据语义重合仅 %.2f —— "
               "编号真实不等于论据成立" % (rel, ln, crit, kind, rid, title[:60], sim))
    return "verified", text, iss


def run(offline=False):
    """返回 (issues, unchecked, verified, skipped)。"""
    cache = _load_cache() if not offline else {}
    refs, skipped = _scan_files()
    issues, unchecked, verified = [], [], []
    for path, ln, kind, rid, line in refs:
        rel = os.path.relpath(path, _ROOT)
        if offline:
            unchecked.append("%s:%d %s:%s（离线未核验）" % (rel, ln, kind, rid))
            continue
        st, text, iss = _check_ref(rel, ln, kind, rid, line, cache)
        (unchecked if st == "unchecked" else verified).append(text)
        if iss:
            issues.append(iss)
    if not refs:
        issues.append("[R21 探针失效] 未扫描到任何 arXiv/DOI 引用——正则失效或引用被清空，不得静默通过")
    issues.extend(_sem_cover())
    if not offline:
        _save_cache(cache)
    return issues, unchecked, verified, skipped


def self_check():
    import base.assertrun as _ar
    chk = _ar.Checker("tools/refcheck")
    # 正则
    chk.eq("能抽 arXiv 号", _ARXIV_RE.findall("arXiv:2410.07296 and arXiv:2604.28025"),
           ["2410.07296", "2604.28025"])
    chk.eq("能抽 DOI", len(_DOI_RE.findall("https://doi.org/10.1000/xyz.2024")), 1)
    # 语义判定：相关标题 vs 无关标题
    hi = _coverage(_SEM["penetration_m"],
                   "Penetration Depth Estimation for Rigid Body Collision Using GJK and EPA")
    lo = _coverage(_SEM["mask_iou"],
                   "Residual-Limb Aware Single-Image 3D Human Mesh Recovery for "
                   "Individuals with Limb Loss residual limb amputee mesh vertices")
    chk.gt("相关文献覆盖率应达阈值", hi, _COVER_MIN)
    chk.lt("无关文献覆盖率应低于阈值(ResiHMR/mask_iou)", lo, _COVER_MIN)
    chk.eq("判据名可从行中识别", _criterion_of('"penetration_m": (0.005, "<", "arXiv:123"'),
           "penetration_m")
    chk.eq("无判据上下文时为 None", _criterion_of("some unrelated line arXiv:1234.5678"), None)
    # 自身测试夹具(假编号)不得计入扫描结果, 否则永远 UNVERIFIED 污染报告
    self_rel = os.path.relpath(os.path.abspath(__file__), _ROOT)
    chk.eq("自身测试夹具不计入", [r for r in _scan_files()[0]
                            if os.path.relpath(r[0], _ROOT) == self_rel], [])
    # 假绿防线: 0 条已核验 + 有未核验 -> 必须判失败(历史上此处曾报 OK)
    chk.eq("0条已核验时不得报通过", verdict_of([], [], ["x"])[0], 1)
    chk.eq("全部核验且无嫌疑时为通过", verdict_of([], ["y"], [])[0], 0)
    chk.eq("有嫌疑时判失败", verdict_of(["s"], ["y"], [])[0], 1)
    chk.eq("部分核验且无嫌疑时为通过", verdict_of([], ["y"], ["x"])[0], 0)
    # 语义词典覆盖度：harness.py 每个判据都必须登记，否则其引用跳过比对误报 OK
    chk.eq("语义词典无缺项", _sem_cover(), [])
    chk.eq("判据名可从行中识别(float_m)", _criterion_of('"float_m": (0.05, "<", "arXiv:2410.07296"'), "float_m")
    return 0 if chk.report(verbose=True) else 1


def verdict_of(issues, verified, unchecked):
    """统一的通过判定。返回 (rc, 说明)。

    单独抽出是为了让 self_check 能直接断言各分支——历史上 main() 内联判定
    漏掉 unchecked, 造成"0 条核验仍报 OK"的假绿, 而这个分支此前无人测过。
    """
    if not verified and unchecked:
        return 1, "[R21 未能完成核验] 已核验 0 条、未核验 %d 条（网络不可达）—— 本次结论无效，不得报通过" % len(unchecked)
    if not issues:
        return 0, "OK  无贴牌嫌疑" + ("" if not unchecked else
                  "（另有 %d 条未核验，未纳入结论）" % len(unchecked))
    return 1, "共 %d 条" % len(issues)


def main():
    if "--self-check" in sys.argv:
        sys.exit(self_check())
    offline = "--offline" in sys.argv
    issues, unchecked, verified, skipped = run(offline=offline)
    print("=== R21 出处核验 ===")
    if skipped:
        print("跳过 %d 条撤除说明（记录的是已撤掉的引用，非当前引用）：" % len(skipped))
        for k in skipped:
            print("  --  " + k)
    print("已核验 %d 条" % len(verified))
    for v in verified:
        print("  OK  " + v)
    if unchecked:
        print("UNVERIFIED %d 条（网络不可达/未取到标题，不等于通过）：" % len(unchecked))
        for u in unchecked:
            print("  ??  " + u)
    # 关键: 结论必须建立在"真的核验过"之上。
    # 历史 bug: 网络 403 导致已核验 0 条、8 条全 UNVERIFIED，却打印
    #   "OK 无贴牌嫌疑" —— 那句 OK 只意味着"没发现嫌疑"，而实际是"什么都没核验"。
    rc, msg = verdict_of(issues, verified, unchecked)
    if rc == 0:
        print(msg)
        return 0
    for s in issues:
        print(s)
    print(msg)
    return 1


if __name__ == "__main__":
    sys.exit(main())
