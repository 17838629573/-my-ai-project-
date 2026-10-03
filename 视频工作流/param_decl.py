"""
param_decl — 参数声明与反问接口

业界依据（真实检索）：
- Fail Fast (P034 / Jim Shore, IEEE Software 2004)
  "缺失的必要配置不得静默降级，须在检测点就近失败"
  "identity/凭据/主机/端口/密钥 永远不该有默认值"
- No Magic Defaults：静默回填掩盖意图 → "开发过了、生产炸"
- Strict Unknown Values (Hypster ADR)：未知参数默认 raise，不是 warn
- Spring Boot ignoreUnknownFields=false
- .NET ErrorOnUnknownConfiguration
- Go json.Decoder.DisallowUnknownFields()
  → 业界三家主流框架一律默认"严格模式"

铁律99  代码内部不存在的参数：
        禁止 AI 心里默算，禁止代码静默兜底。
        必须由代码反问 AI，AI 以「值 + 搜证来源 + 合理区间」作答，
        落盘为可审计的 params_ai.json 后由代码运算。
铁律100 AI 提供的物理常数无来源引用 → 拒绝（防幻觉）。
铁律101 参数必须带合理区间，越界拒绝（防数量级错误）。
"""

import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
PARAMS_FILE = os.path.join(_HERE, "params_ai.json")


class AskAI(Exception):
    """参数缺失 —— 抛给 AI 的结构化反问。禁止静默兜底。"""

    def __init__(self, name, family, why, unit_hint="", hint=""):
        self.name = name
        self.family = family
        self.why = why
        self.unit_hint = unit_hint
        self.hint = hint
        super().__init__(self.prompt())

    def prompt(self):
        return (
            "【代码反问 AI —— 参数缺失，禁止心里默算】\n"
            "参数名 : %s\n"
            "所属族 : %s\n"
            "单位   : %s\n"
            "为何需要: %s\n"
            "%s\n"
            "\n你必须做（四件事，缺一不可）：\n"
            "  1. 联网检索该物理量的权威取值，给出数值\n"
            "  2. 给出来源（文献名 / 标准号 / 厂商文档名）\n"
            "  3. 给出合理区间 [lo, hi]\n"
            "  4. 落盘写入 params_ai.json：\n"
            '     "%s": {"value": <数>, "unit": "...",\n'
            '             "source": "...", "range": [lo, hi],\n'
            '             "family": "%s"}\n'
            "\n禁止：凭印象给数、不写来源、拿别物体的值代替、在脑子里算完直接给结果。\n"
            "必须由代码读取该参数并运算 —— 你只负责提供数值和来源。\n"
            % (self.name, self.family, self.unit_hint or "（须由 AI 声明）",
               self.why, self.hint, self.name, self.family)
        )


class ParamRejected(Exception):
    """AI 提供的参数不合规 —— 缺来源 / 缺区间 / 越界 / 类型错。"""


def _load():
    if not os.path.exists(PARAMS_FILE):
        return {}
    with open(PARAMS_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def verify(pname, p):
    """校验 AI 提供的参数：值 / 单位 / 来源 / 区间 四件套。缺一即拒。"""
    if not isinstance(p, dict):
        raise ParamRejected("%s: 必须是 dict，实为 %s" % (pname, type(p).__name__))
    for key in ("value", "unit", "source", "range", "family"):
        if key not in p:
            raise ParamRejected("%s: 缺字段 %r（防幻觉：五项缺一不可）" % (pname, key))
    v = p["value"]
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ParamRejected("%s: value 必须是数值，实为 %r" % (pname, v))
    if not str(p["source"]).strip():
        raise ParamRejected("%s: source 为空 —— 无来源拒绝（铁律100）" % pname)
    rg = p["range"]
    if not (isinstance(rg, (list, tuple)) and len(rg) == 2):
        raise ParamRejected("%s: range 必须是 [lo, hi]" % pname)
    lo, hi = float(rg[0]), float(rg[1])
    if not lo < hi:
        raise ParamRejected("%s: range 需 lo < hi，实为 %s" % (pname, rg))
    if not (lo <= float(v) <= hi):
        raise ParamRejected(
            "%s: value=%s 越界 [%s, %s] —— 疑似数量级错误（铁律101）" % (pname, v, lo, hi))
    return float(v)


def require(pname, family, why, unit_hint="", hint=""):
    """
    读取参数。不存在 → 抛 AskAI（反问，不兜底）。
    存在但 AI 填得不合规 → 抛 ParamRejected（防幻觉）。
    """
    store = _load()
    if pname not in store:
        raise AskAI(pname, family, why, unit_hint, hint)
    return verify(pname, store[pname])


def have(pname):
    """参数是否已声明（不抛异常）。"""
    return pname in _load()


def save(pname, value, unit, source, rng, family):
    """把 AI 作答落盘。写入前先验一次，脏数据不入库。"""
    verify(pname, {"value": value, "unit": unit, "source": source,
                   "range": rng, "family": family})
    store = _load()
    store[pname] = {"value": value, "unit": unit, "source": source,
                    "range": list(rng), "family": family}
    with open(PARAMS_FILE, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    return store[pname]


def audit():
    """审计：列出所有已声明参数的来源与区间。无来源的会被 verify 拦。"""
    store = _load()
    report, bad = [], []
    for k in sorted(store):
        try:
            v = verify(k, store[k])
            report.append((k, v, store[k]["unit"], store[k]["source"], store[k]["family"]))
        except ParamRejected as e:
            bad.append(str(e))
    return report, bad


def self_check():
    """自检 8 项，含 2 项证伪。"""
    ok = []
    bak = None
    if os.path.exists(PARAMS_FILE):
        with open(PARAMS_FILE, "r", encoding="utf-8") as f:
            bak = f.read()

    def ck(name, cond, detail=""):
        ok.append((name, bool(cond), detail))
        return bool(cond)

    # 1 缺失参数必须抛 AskAI，不是返回默认值
    try:
        require("_不存在的参数_XYZ", "test", "自检用")
        ck("1 缺失→抛AskAI", False, "居然没抛，静默通过了")
    except AskAI as e:
        ck("1 缺失→抛AskAI", True, "抛了 AskAI")

    # 2 反问内容必须含四要素（名/来源要求/区间要求/落盘格式）
    try:
        require("_不存在的参数_XYZ", "test", "自检用")
        p = ""
    except AskAI as e:
        p = e.prompt()
    ck("2 反问含来源要求", "source" in p and "来源" in p, "")
    ck("3 反问含区间要求", "range" in p and "区间" in p, "")
    ck("4 反问含落盘格式", "params_ai.json" in p, "")

    # 5 无来源 → 拒绝（防幻觉）
    save("_t_nosrc", 1.0, "m", "   ", [0, 2], "test") if False else None
    try:
        verify("_t_nosrc", {"value": 1.0, "unit": "m", "source": "  ",
                            "range": [0, 2], "family": "test"})
        ck("5 无来源→拒绝", False, "空来源被放过了")
    except ParamRejected:
        ck("5 无来源→拒绝", True, "空来源被拒")

    # 6 越界 → 拒绝（防数量级错误）
    try:
        verify("_t_oor", {"value": 9999.0, "unit": "m", "source": "x",
                          "range": [0, 2], "family": "test"})
        ck("6 越界→拒绝", False, "越界值被放过")
    except ParamRejected:
        ck("6 越界→拒绝", True, "越界值被拒")

    # 7 合规参数能存能取且参与运算
    save("_t_ok", 2.5, "m", "自检构造", [0, 10], "test")
    got = require("_t_ok", "test", "自检")
    ck("7 合规→可取", abs(got - 2.5) < 1e-12, "读出 %s" % got)
    ck("8 参与运算", abs(got * 2 - 5.0) < 1e-12, "2.5*2=5.0")

    # 证伪A：AST 扫 require 源码，确认不存在"返回数字常量"的兜底路径。
    # （只在函数体里 try/except 是空转 —— 必须查真实实现。）
    import ast as _ast
    with open(os.path.join(_HERE, "param_decl.py"), "r", encoding="utf-8") as f:
        _src = f.read()
    _tree = _ast.parse(_src)
    _fn = next((n for n in _ast.walk(_tree)
                if isinstance(n, _ast.FunctionDef) and n.name == "require"), None)
    _bad = []
    if _fn is None:
        _bad.append("找不到 require")
    else:
        for node in _ast.walk(_fn):
            if isinstance(node, _ast.Return) and node.value is not None:
                v = node.value
                # 合法：return verify(...)  非法：return 1.0 / x or 1.0
                is_call = isinstance(v, _ast.Call) and \
                    getattr(v.func, "id", "") == "verify"
                is_num = isinstance(v, _ast.Constant) and isinstance(v.value, (int, float))
                is_or = isinstance(v, _ast.BoolOp) or isinstance(v, _ast.IfExp)
                if is_num or is_or or not is_call:
                    _bad.append("L%d" % node.lineno)
    ck("证伪A require无静默兜底", not _bad,
       "无兜底路径" if not _bad else "发现兜底: %s" % _bad)

    # 清理自检污染
    store = _load()
    store.pop("_t_ok", None)
    with open(PARAMS_FILE, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)

    # 证伪B：verify 全放行 = 空转
    try:
        verify("_t_all", {"value": "abc", "unit": "", "source": "",
                          "range": [5, 1], "family": "t"})
        ck("证伪B 脏数据被抓", False, "脏数据全放行 —— verify 空转")
    except ParamRejected:
        ck("证伪B 脏数据被抓", True, "")

    return ok


if __name__ == "__main__":
    res = self_check()
    npass = sum(1 for _, c, _ in res if c)
    for n, c, d in res:
        print("%s %s %s" % ("PASS" if c else "FAIL", n, d))
    print("---- %d/%d PASS ----" % (npass, len(res)))
