#!/usr/bin/env python3
"""
执行门禁 — 将不可绕过的硬规则固化为代码执行。

退出码：
  0 = 通过
  1 = 硬规则违例（调用方应 halt）
  2 = 用法错误

子命令：
  gate pre-step <step_name>        步骤前门禁：前置检查
  gate post-step <step_name>       步骤后门禁：产出完整性
  check-write <filepath>           写文件门禁：红黄区保护（铁律5）
  check-auth <track_path>          授权门禁：track 存在且有效（铁律8）
  check-iron-law <filepath>        铁律保护门禁（铁律9）
  check-evidence <exit_code> [msg] 判定依据验证（铁律1）
"""

import os
import re
import sys
import shutil
import hashlib
from datetime import datetime, timedelta


# ── 常量 ─────────────────────────────────────────────

RED_ZONE_PATTERNS = [
    r'(^|/)\.env',        # .env / path/.env
    r'(^|/)auth(\b|/|$)',  # 修复：原无词边界，src/author.py 也被判红区
    r'(^|/)secrets?',     # secret/ secrets/
    r'(^|/)deploy',       # deploy/
    r'(^|/)ci/',          # ci/ 目录
    r'(^|/)\.github/workflows/',   # 修复：README 声称保护 CI 配置，正则里却没有
    r'(^|/)\.gitlab-ci\.yml$',
    r'(^|/)requirements\.txt$',
    r'(^|/)Pipfile$',
    r'(^|/)package-lock\.json$',
    r'(^|/)yarn\.lock$',
    r'(^|/)go\.mod$',
    r'(^|/)\.gitignore$',
]

# 核心区：门禁自身与规则本体。改这里 = 改游戏规则
# 铁律10：修改前必须停下向用户说明「发现什么问题 + 拟怎么改」，
#         取得【单次有效】授权；永久授权对核心区无效。
CORE_ZONE_PATTERNS = [
    r'(^|/)' + re.escape('CORELOG.md') + r'$',
    r'(^|/)tracks/.*\.track\.md$',           # 授权文件: 防 AI 自造永久授权
    r'(^|/)skills/.*\.track\.md$',        # 留痕本身: 防伪造信任
    r'(^|/)\.workflow-baseline/.*$',                  # 基线副本: 防篡改回滚点
    r'(^|/)scripts/enforce\.py$',
    r'(^|/)scripts/dep_check\.py$',
    r'(^|/)WORKFLOW\.md$',
    r'(^|/)SKILL\.md$',
    r'(^|/)skills/.*/SKILL\.md$',
]

YELLOW_ZONE_PATTERNS = [
    r'(^|/)config\.',
    r'(^|/)settings\.',
    r'(^|/)routes?\.',
    r'(^|/)models?\.',
    r'(^|/)migrations?/',
    r'(^|/)main\.',
    r'(^|/)app\.',
    r'(^|/)index\.',
]

WORKFLOW_FILE = "WORKFLOW.md"
# 铁律正文指纹：每条至少一个核心词，改正文即失效（防"改内容不改标题"绕过）
IRON_LAW_FINGERPRINTS = {
    1: r'命令输出|退出码',
    2: r'必要范围|不顺手',
    3: r'留产物|无产物',
    4: r'先搜|不自造',
    5: r'红区|黄区',
    6: r'halt|ERRORS',
    7: r'估耗时|悬空',
    8: r'\.track\.md|授权',
    9: r'不可被.*覆盖|不可逆',
}

IRON_LAW_PATTERN = re.compile(r'^\s*#+.*铁律', re.MULTILINE)
WORKLOG_FILE = "WORKLOG.md"

CORELOG_FILE  = "CORELOG.md"
BASELINE_DIR  = ".workflow-baseline"
PROMOTE_L2    = 10   # 有效次数 ≥ 此值 → 允许半永久
PROMOTE_L3    = 5    # 半永久后继续有效 ≥ 此值 → 允许永久

SKILL_DIR = "skills"
TRACK_DIR = "tracks"


# ── 辅助 ─────────────────────────────────────────────

def _abs_path(p: str) -> str:
    """确保有工作目录锚定，不依赖 cwd"""
    cwd = os.environ.get("WORKFLOW_ROOT", os.getcwd())
    if not os.path.isabs(p):
        p = os.path.join(cwd, p)
    return os.path.normpath(p)

def _relative_to_root(p: str) -> str:
    """把绝对路径转为相对工作根目录的路径"""
    cwd = os.environ.get("WORKFLOW_ROOT", os.getcwd())
    try:
        return os.path.relpath(p, cwd)
    except ValueError:
        return p

def _path_matches_any(path: str, patterns: list) -> bool:
    """path 是否命中任一正则模式"""
    for pat in patterns:
        if re.search(pat, path, re.IGNORECASE):
            return True
    return False

def _find_track_file(track_name: str) -> str:
    """查找 .track.md 文件。track_name 可以是完整路径或名字"""
    cwd = os.environ.get("WORKFLOW_ROOT", os.getcwd())
    if track_name.endswith(".track.md"):
        candidates = [
            track_name,
            os.path.join(cwd, track_name),
            os.path.join(cwd, TRACK_DIR, track_name),
        ]
    else:
        candidates = [
            os.path.join(cwd, f"{track_name}.track.md"),
            os.path.join(cwd, TRACK_DIR, f"{track_name}.track.md"),
            os.path.join(cwd, SKILL_DIR, track_name, f"{track_name}.track.md"),
        ]
    for c in candidates:
        p = _abs_path(c)
        if os.path.isfile(p):
            return p
    return ""

def _parse_track_expiry(track_path: str) -> str:
    """从 .track.md 中解析到期状态：'valid' / 'expired' / 'permanent' / 'invalid'"""
    if not track_path or not os.path.isfile(track_path):
        return "no_file"
    try:
        content = open(track_path, encoding="utf-8").read()
    except Exception:
        return "unreadable"

    # 查找到期日
    m = re.search(r'到期日:\s*(\S+)', content)
    if not m:
        return "no_expiry_field"

    expiry_str = m.group(1).strip()
    if expiry_str == "-":
        return "permanent"  # 永久
    if expiry_str == "项目结束":
        return "valid"  # 临时，项目结束前始终有效

    try:
        expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
    except ValueError:
        return "bad_date_format"

    if expiry_date >= datetime.now().date():
        return "valid"
    else:
        return "expired"


# ══════════════════════════════════════════════════════
# 子命令实现
# ══════════════════════════════════════════════════════

def cmd_gate_pre_step(step_name: str) -> int:
    """步骤前门禁：检查前置条件"""
    cwd = os.environ.get("WORKFLOW_ROOT", os.getcwd())
    worklog = os.path.join(cwd, WORKLOG_FILE)
    
    checks = 0
    ok = 0
    
    # 1. WORKLOG 存在？没有就创建
    checks += 1
    if not os.path.isfile(worklog):
        print(f"[enforce] ⚠️ {WORKLOG_FILE} 不存在 → 自动创建")
        try:
            with open(worklog, "w", encoding="utf-8") as f:
                f.write(f"# WORKLOG\n\n")
            print(f"[enforce] ✓ 已创建 {WORKLOG_FILE}")
        except Exception as e:
            print(f"[enforce] ✗ 创建 WORKLOG 失败: {e}")
            return 1
    ok += 1
    
    # 2. 检查铁律文件本身是否被修改过（通过 dep_check.py 间接保护）
    checks += 1
    wf_path = os.path.join(cwd, WORKFLOW_FILE)
    if os.path.isfile(wf_path):
        ok += 1
    
    # 3. 如果这不是第一步，检查上一步的 worklog 条目
    checks += 1
    if step_name not in ("0", "1", "推荐", "接需求", "入口"):
        try:
            content = open(worklog, encoding="utf-8").read().strip()
            if content and content != "# WORKLOG":
                ok += 1
            else:
                print(f"[enforce] ⚠️ {WORKLOG_FILE} 为空，步骤 {step_name} 无前置断点记录")
                # 只是警告，不阻断
        except Exception:
            pass
    else:
        ok += 1
    
    print(f"[enforce] gate pre-step [{step_name}]: {ok}/{checks} 通过")
    # pre-step 设计为警告模式不阻断（首次运行 WORKLOG 为空属正常），
    # 但显式返回 0 避免死代码误导维护者
    return 0


def cmd_gate_post_step(step_name: str) -> int:
    """步骤后门禁：必须追加 WORKLOG（断点强制）"""
    cwd = os.environ.get("WORKFLOW_ROOT", os.getcwd())
    worklog = os.path.join(cwd, WORKLOG_FILE)
    
    if not os.path.isfile(worklog):
        print(f"[enforce] ✗ {WORKLOG_FILE} 不存在！步骤后必须写断点")
        print(f"[enforce] → 请追加一行：`{datetime.now().strftime('%Y-%m-%d %H:%M')} | 步骤{step_name} | 完成`")
        return 1

    content = open(worklog, encoding="utf-8").read()
    if f"步骤{step_name}" not in content:
        print(f"[enforce] ✗ WORKLOG 中无步骤 {step_name} 记录！")
        print(f"[enforce] → 请追加：`{datetime.now().strftime('%Y-%m-%d %H:%M')} | 步骤{step_name} | 过门产物`")
        return 1
    
    # 修复：原版只要出现「步骤N」四字就放行，写"测试失败,卡住"也过门
    for line in content.splitlines():
        if f"步骤{step_name}" in line:
            if re.search(r'失败|卡住|未完成|报错|阻断|error|failed|挂了', line, re.I):
                print(f"[enforce] ✗ 步骤 {step_name} 的 WORKLOG 是【失败/未完成】记录，不得过门")
                print(f"[enforce]   记录：{line.strip()[:80]}")
                print(f"[enforce]   → 按 halt 协议停下：修好再过门，或走四选项交用户裁定")
                return 1

    print(f"[enforce] ✓ WORKLOG 已记录步骤 {step_name}")
    return 0


def cmd_check_write(filepath: str) -> int:
    """写文件门禁：铁律5 红黄区保护 + 铁律10 核心区保护"""
    path = _abs_path(filepath)
    rel = _relative_to_root(path)

    if not os.path.exists(path):
        pass  # 新建文件不检查

    # ── 铁律10 核心区：最高优先级，先于红区判定 ──
    if _path_matches_any(rel, CORE_ZONE_PATTERNS):
        return _core_zone_gate(rel)

    # 检查红区
    if _path_matches_any(rel, RED_ZONE_PATTERNS):
        target = rel.split("/")[-1]
        # 查找对应 track
        track = _find_track_file(target)
        status = _parse_track_expiry(track)
        if status not in ("valid", "permanent"):
            print(f"[enforce] ✗ 铁律5 违例：{rel} 属于【红区文件】")
            print(f"[enforce]   红区: .env / auth / secrets / deploy / CI 配置 / 依赖锁文件")
            print(f"[enforce]   未经授权禁止自动修改！请先按 track 流程获取批准。")
            return 1
        print(f"[enforce] ✓ {rel} 红区文件，已有授权")
        return 0

    # 检查黄区 — 仅警告不阻断
    if _path_matches_any(rel, YELLOW_ZONE_PATTERNS):
        print(f"[enforce] ⚠️ {rel} 属于【黄区文件】，改前应告知用户")
        print(f"[enforce]   黄区: config / settings / routes / models / migrations / 入口文件")
        return 0
    
    return 0


def _baseline_path(rel: str) -> str:
    return os.path.join(_abs_path(BASELINE_DIR), rel)


def _file_sha256(filepath: str) -> str:
    """计算文件 SHA-256 哈希"""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _ensure_baseline(rel: str) -> str:
    """首次改动前冻结原文件到基线；已冻结则永不再动（基线只读）"""
    src, dst = _abs_path(rel), _baseline_path(rel)
    if os.path.isfile(dst) or not os.path.isfile(src):
        return dst if os.path.isfile(dst) else ""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    print(f"[enforce] ◆ 已冻结基线 {BASELINE_DIR}/{rel}（原文件副本，只读）")
    return dst


def _corelog_rows():
    p = _abs_path(CORELOG_FILE)
    if not os.path.isfile(p):
        return []
    out = []
    for line in open(p, encoding="utf-8"):
        line = line.strip()
        if line.startswith("|") and "---" not in line:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 4 and cells[0] != "时间":
                out.append(cells)
    return out


def _trust_level(rel: str):
    """依据留痕判定信任档位：L1 单次 / L2 半永久 / L3 永久"""
    rows = [r for r in _corelog_rows() if r[1] == rel]
    eff = sum(1 for r in rows if "有效" in r[2])
    if eff < PROMOTE_L2:
        return 1, eff
    # 找到最近一次「半永久启用」之后的记录
    idx = max([i for i, r in enumerate(rows) if "半永久启用" in r[2]] or [-1])
    tail = rows[idx + 1:] if idx >= 0 else []
    if not tail:
        return 2, eff
    eff2 = sum(1 for r in tail if "有效" in r[2])
    rolled = any("回滚" in r[2] for r in tail)
    if eff2 >= PROMOTE_L3 and not rolled:
        return 3, eff
    return 2, eff


def _corelog_append(rel: str, result: str, score: str, note: str):
    p = _abs_path(CORELOG_FILE)
    fresh = not os.path.isfile(p)
    if fresh:
        open(p, "w", encoding="utf-8").write(
            "# 核心区改动留痕（铁律10）\n\n"
            "| 时间 | 文件 | 结果 | 自检分数 | 说明 |\n"
            "| --- | --- | --- | --- | --- |\n")
    open(p, "a", encoding="utf-8").write(
        f"| {datetime.now().strftime('%Y-%m-%d %H:%M')} | {rel} | {result} "
        f"| {score} | {note} |\n")


def cmd_rollback(rel: str) -> int:
    """回滚核心区文件到冻结基线，并留痕"""
    dst = _baseline_path(rel)
    if not os.path.isfile(dst):
        print(f"[enforce] ✗ 无基线可回滚：{BASELINE_DIR}/{rel}")
        return 1
    shutil.copy2(dst, _abs_path(rel))
    _corelog_append(rel, "回滚", "-", f"已恢复至初始基线")
    print(f"[enforce] ✓ 已回滚 {rel} → 初始基线（信任档位重置为 L1 单次）")
    return 0


def _core_zone_gate(rel: str) -> int:
    """铁律10 核心区闸门：halt 停下报用户 + track 授权 + 留痕升级"""
    level, eff = _trust_level(rel)
    target = rel.replace("/", "_")
    track = _find_track_file(target)

    _ensure_baseline(rel)

    if not track:
        print(f"[enforce] ✗ 铁律10 违例：{rel} 属于【核心区】= 规则与门禁本体")
        print(f"[enforce]   → 按 halt 协议停下，向用户报四项：")
        print(f"[enforce]     ① 卡在哪步  ② 已试过什么")
        print(f"[enforce]     ③ 发现什么问题（附命令输出）④ 拟怎么改")
        print(f"[enforce]   → 当前信任档位 L{level}（累计有效 {eff} 次）")
        print(f"[enforce]     L1 单次 / L2 半永久(有效≥{PROMOTE_L2}) / L3 永久(半永久后再有效≥{PROMOTE_L3})")
        return 1

    content = open(track, encoding="utf-8").read()
    is_once     = bool(re.search(r'(有效期|次数|答)\s*[:：]\s*单次', content))
    is_semiperm = bool(re.search(r'(有效期|答)\s*[:：]\s*半永久', content))
    is_perm     = bool(re.search(r'(有效期|答)\s*[:：]\s*永久', content))

    if level == 1 and not is_once:
        print(f"[enforce] ✗ 铁律10 违例：{rel} 信任档位 L1，只接受【单次】授权")
        print(f"[enforce]   累计有效 {eff}/{PROMOTE_L2}，未达半永久门槛")
        return 1
    if level == 2 and is_perm:
        print(f"[enforce] ✗ 铁律10 违例：{rel} 信任档位 L2，尚不接受【永久】授权")
        print(f"[enforce]   需半永久后继续有效 ≥{PROMOTE_L3} 次且无回滚")
        return 1
    if level >= 2 and is_once and level == 2:
        pass  # L2 也接受单次，允许保守用

    st = _parse_track_expiry(track)
    if st not in ("valid", "permanent"):
        print(f"[enforce] ✗ 铁律10 违例：{rel} 授权状态={st}")
        return 1

    kind = "单次" if is_once else ("半永久" if is_semiperm else "永久")
    if is_semiperm:
        _corelog_append(rel, "半永久启用", "-", "信任升级 L1→L2")
    print(f"[enforce] ✓ {rel} 核心区【{kind}】授权有效（信任档位 L{level}，累计有效 {eff}）")
    print(f"[enforce]   改后必跑：python3 selftest.py 且分数不降")
    print(f"[enforce]   改后必记：enforce.py log-effect {rel} 有效|无效 <分数> <说明>")
    return 0


def cmd_check_auth(track_name: str) -> int:
    """授权门禁：铁律8 track 存在且有效"""
    track_file = _find_track_file(track_name)
    status = _parse_track_expiry(track_file)
    
    if status == "no_file":
        print(f"[enforce] ✗ 铁律8 违例：未找到授权记录 `{track_name}.track.md`")
        print(f"[enforce]   必须按 track/SKILL.md 先获取用户授权再执行")
        return 1
    
    if status == "unreadable":
        print(f"[enforce] ✗ 铁律8 违例：授权文件 `{track_file}` 无法读取")
        return 1
    
    if status == "expired":
        print(f"[enforce] ✗ 铁律8 违例：授权 `{track_file}` 已过期")
        print(f"[enforce]   必须重新向用户确认授权")
        return 1
    
    if status == "no_expiry_field":
        print(f"[enforce] ✗ 铁律8 违例：授权文件 `{track_file}` 缺少到期日")
        return 1
    
    if status == "bad_date_format":
        print(f"[enforce] ✗ 铁律8 违例：授权文件 `{track_file}` 到期日格式错误")
        return 1
    
    if status == "permanent":
        print(f"[enforce] ✓ 授权 `{track_name}` 永久有效")
        return 0
    
    # valid
    print(f"[enforce] ✓ 授权 `{track_name}` 有效")
    return 0


def cmd_check_iron_law(filepath: str) -> int:
    """铁律保护门禁：铁律9 — 禁止覆盖或删除铁律"""
    path = _abs_path(filepath)
    rel = _relative_to_root(path)
    
    # 只保护 WORKFLOW.md 中的铁律
    if os.path.basename(path) != "WORKFLOW.md":
        return 0
    
    if not os.path.isfile(path):
        return 0
    
    try:
        content = open(path, encoding="utf-8").read()
    except Exception:
        return 0
    
    # 检查铁律节是否存在
    if not IRON_LAW_PATTERN.search(content):
        print(f"[enforce] ✗ 铁律9 违例：{rel} 中铁律章节丢失或被移除！")
        print(f"[enforce]   铁律是所有步骤的强制约束，不可被删除或覆盖")
        return 1
    
    # 检查铁律数量是否被删减
    law_count = len(re.findall(r'^\d+\.', content, re.MULTILINE))
    if law_count < 9:
        print(f"[enforce] ✗ 铁律9 违例：{rel} 仅有 {law_count} 条铁律（应有 ≥9 条）")
        print(f"[enforce]   铁律不可被删除或缩减")
        return 1

    # 修复：原版只查「标题+编号」，改正文不改标题即可绕过
    # 改为校验每条铁律正文的关键指纹（每条至少一个不可替换的核心词）
    body = content[IRON_LAW_PATTERN.search(content).end():]
    body = body.split("\n## ")[0]
    lines = [l.strip() for l in body.splitlines() if re.match(r'^\d+\.', l.strip())]
    missing = []
    for idx, fp in IRON_LAW_FINGERPRINTS.items():
        seg = " ".join(lines[idx-1:idx]) if idx-1 < len(lines) else ""
        if not seg or not re.search(fp, seg):
            missing.append(idx)
    if missing:
        print(f"[enforce] ✗ 铁律9 违例：{rel} 铁律正文被改写（第 {missing} 条）")
        print(f"[enforce]   铁律标题与编号完好，但正文已被替换 —— 保护的是内容，不只是标题")
        print(f"[enforce]   → 按铁律10：改核心区须停下报用户，取单次授权")
        return 1

    print(f"[enforce] ✓ {rel} 铁律完整（{law_count} 条，正文指纹校验通过）")
    return 0


def cmd_check_evidence(exit_code_str: str, msg: str = "") -> int:
    """判定依据验证：铁律1 — 判定必须基于命令输出"""
    try:
        code = int(exit_code_str)
    except ValueError:
        print(f"[enforce] ✗ 铁律1 违例：exit_code 应为整数，收到 '{exit_code_str}'")
        return 1
    
    # 修复：原版只校验「是不是整数」，传失败退出码照样放行，铁律1形同虚设
    if code != 0:
        print(f"[enforce] ✗ 铁律1 违例：退出码 {code} ≠ 0，判定未通过不得过门")
        print(f"[enforce]   先把命令修到退出码 0 再过门；不得用失败结果续做")
        return 1

    if not msg or msg.strip() == "":
        print(f"[enforce] ⚠️ 铁律1 建议：判定应附带依据说明，当前无描述")
        return 0
    
    print(f"[enforce] ✓ 判定依据：退出码 {code} | {msg.strip()}")
    return 0


def cmd_validate_checklist() -> int:
    """全局完整性检查：验证所有硬规则的状态"""
    cwd = os.environ.get("WORKFLOW_ROOT", os.getcwd())
    
    issues = 0
    
    # 1. WORKFLOW.md 铁律完整性
    wf_path = os.path.join(cwd, WORKFLOW_FILE)
    if os.path.isfile(wf_path):
        r = cmd_check_iron_law(wf_path)
        if r != 0:
            issues += 1
    else:
        print(f"[enforce] ✗ {WORKFLOW_FILE} 缺失")
        issues += 1
    
    # 2. WORKLOG 存在
    wl_path = os.path.join(cwd, WORKLOG_FILE)
    if not os.path.isfile(wl_path):
        print(f"[enforce] ⚠️ {WORKLOG_FILE} 缺失（首次运行可忽略）")
    
    # 3. dep_check.py 存在
    dep_path = os.path.join(cwd, "scripts", "dep_check.py")
    if not os.path.isfile(dep_path):
        print(f"[enforce] ✗ scripts/dep_check.py 缺失")
        issues += 1
    else:
        print(f"[enforce] ✓ scripts/dep_check.py 存在")
    
    # 4. enforce.py 自身哈希校验（P0-2 防 AI 自改门禁）
    #    对比当前脚本与冻结基线，不一致 = 门禁已被篡改
    enforce_path = os.path.abspath(__file__)
    baseline_enforce = _baseline_path("scripts/enforce.py")
    if os.path.isfile(baseline_enforce):
        cur_hash = _file_sha256(enforce_path)
        base_hash = _file_sha256(baseline_enforce)
        if cur_hash != base_hash:
            print(f"[enforce] ✗ 铁律10 违例：scripts/enforce.py 已被篡改（与基线哈希不一致）")
            print(f"[enforce]   恢复：sh scripts/restore.sh scripts/enforce.py")
            issues += 1
        else:
            print(f"[enforce] ✓ scripts/enforce.py 自身哈希校验通过（未被篡改）")
    else:
        # 基线尚未生成（从未触发过核心区闸门），至少声明自身在运行
        print(f"[enforce] ✓ scripts/enforce.py 在运行（基线未冻结，首次改核心区时自动冻结）")
    
    if issues > 0:
        print(f"[enforce] ✗ {issues} 项硬规则违例")
        return 1
    print(f"[enforce] ✓ 全局完整性检查通过")
    return 0


def cmd_clean_temp() -> int:
    """清理所有标记为"项目结束"的临时授权条目"""
    cwd = os.environ.get("WORKFLOW_ROOT", os.getcwd())
    removed = 0
    skipped = 0

    # 扫描所有 .track.md 文件
    for root, dirs, files in os.walk(cwd):
        # 跳过隐藏目录和 .git
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '.git']
        for f in files:
            if not f.endswith('.track.md'):
                continue
            fp = os.path.join(root, f)
            try:
                with open(fp, encoding='utf-8') as fh:
                    content = fh.read()
            except Exception:
                continue

            # 找到所有标记为"项目结束"的条目块
            # 条目块格式：从 "问:" 开始到下一个 "问:" 或文件结尾
            blocks = re.split(r'\n(?=问:)', content.strip())
            kept = []
            for block in blocks:
                if re.search(r'到期日:\s*项目结束', block):
                    # 提取摘要用于日志
                    summary = block.split('\n')[0][:60]
                    print(f"[enforce] ~ 清理临时授权: {summary}")
                    removed += 1
                else:
                    kept.append(block)

            if len(kept) == len(blocks):
                continue  # 没变化

            new_content = '\n\n'.join(kept) + '\n' if kept else ''
            new_content = new_content.strip()

            if not new_content:
                os.remove(fp)
                print(f"[enforce] ✓ 已删除空授权文件: {_relative_to_root(fp)}")
            else:
                with open(fp, 'w', encoding='utf-8') as fh:
                    fh.write(new_content + '\n')
                print(f"[enforce] ✓ 已清理临时授权: {_relative_to_root(fp)}")

    if removed == 0:
        print("[enforce] ✓ 无临时授权需要清理")
    else:
        print(f"[enforce] ✓ 共清理 {removed} 条临时授权")
    return 0


# ══════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════

USAGE = """用法:
  enforce.py gate pre-step <步骤名>    步骤前门禁
  enforce.py gate post-step <步骤名>   步骤后门禁（WORKLOG 强制）
  enforce.py check-write <文件路径>    写文件门禁（铁律5 红黄区）
  enforce.py check-auth <track名>      授权门禁（铁律8）
  enforce.py check-iron-law <文件路径>  铁律保护门禁（铁律9）
  enforce.py check-evidence <退出码> [依据描述]  判定依据验证（铁律1）
  enforce.py validate                    全局完整性检查
  enforce.py log-effect <文件> 有效|无效 <分数> <说明>   核心区改动留痕
  enforce.py rollback <文件>             回滚核心区文件到初始基线
  enforce.py core-status                 查看核心区信任档位
  enforce.py clean-temp                  清理临时授权（步骤7交付前调用）
  enforce.py help                        本帮助
"""

def main():
    if len(sys.argv) < 2:
        print(USAGE)
        sys.exit(2)
    
    cmd = sys.argv[1]
    
    if cmd == "gate":
        if len(sys.argv) < 4:
            print("用法: enforce.py gate <pre-step|post-step> <步骤名>")
            sys.exit(2)
        sub = sys.argv[2]
        step = sys.argv[3]
        if sub == "pre-step":
            sys.exit(cmd_gate_pre_step(step))
        elif sub == "post-step":
            sys.exit(cmd_gate_post_step(step))
        else:
            print(f"未知子命令: gate {sub}")
            sys.exit(2)
    
    elif cmd == "check-write":
        if len(sys.argv) < 3:
            print("用法: enforce.py check-write <文件路径>")
            sys.exit(2)
        sys.exit(cmd_check_write(sys.argv[2]))
    
    elif cmd == "check-auth":
        if len(sys.argv) < 3:
            print("用法: enforce.py check-auth <track名>")
            sys.exit(2)
        sys.exit(cmd_check_auth(sys.argv[2]))
    
    elif cmd == "check-iron-law":
        if len(sys.argv) < 3:
            print("用法: enforce.py check-iron-law <文件路径>")
            sys.exit(2)
        sys.exit(cmd_check_iron_law(sys.argv[2]))
    
    elif cmd == "check-evidence":
        if len(sys.argv) < 3:
            print("用法: enforce.py check-evidence <退出码> [描述]")
            sys.exit(2)
        msg = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else ""
        sys.exit(cmd_check_evidence(sys.argv[2], msg))
    
    elif cmd == "validate":
        sys.exit(cmd_validate_checklist())
    
    elif cmd == "log-effect":
        if len(sys.argv) < 5:
            print("用法: enforce.py log-effect <文件> 有效|无效 <自检分数> <说明>")
            sys.exit(2)
        rel = _relative_to_root(_abs_path(sys.argv[2]))
        _corelog_append(rel, sys.argv[3], sys.argv[4], " ".join(sys.argv[5:]))
        lv, eff = _trust_level(rel)
        print(f"[enforce] ✓ 已留痕 {rel} → {sys.argv[3]}  信任档位 L{lv}（累计有效 {eff}）")
        sys.exit(0)

    elif cmd == "rollback":
        if len(sys.argv) < 3:
            print("用法: enforce.py rollback <核心区文件>  # 回滚到冻结基线")
            sys.exit(2)
        sys.exit(cmd_rollback(_relative_to_root(_abs_path(sys.argv[2]))))

    elif cmd == "core-status":
        cwd = os.environ.get("WORKFLOW_ROOT", os.getcwd())
        print(f"{'文件':<28}{'信任档位':>10}{'累计有效':>10}")
        for rel in ["scripts/enforce.py", "scripts/dep_check.py", "WORKFLOW.md",
                    "SKILL.md"]:
            lv, eff = _trust_level(rel)
            print(f"{rel:<28}{'L'+str(lv):>10}{eff:>10}")
        sys.exit(0)

    elif cmd == "clean-temp":
        sys.exit(cmd_clean_temp())
    
    elif cmd in ("help", "--help", "-h"):
        print(USAGE)
        sys.exit(0)
    
    else:
        print(f"未知命令: {cmd}")
        print(USAGE)
        sys.exit(2)


if __name__ == "__main__":
    main()
