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
from datetime import datetime, timedelta


# ── 常量 ─────────────────────────────────────────────

RED_ZONE_PATTERNS = [
    r'(^|/)\.env',        # .env / path/.env
    r'(^|/)auth',         # auth/ 目录
    r'(^|/)secrets?',     # secret/ secrets/
    r'(^|/)deploy',       # deploy/
    r'(^|/)ci/',          # .github/workflows 等 CI 配置
    r'(^|/)\.gitlab-ci\.yml$',
    r'(^|/)requirements\.txt$',
    r'(^|/)Pipfile$',
    r'(^|/)package-lock\.json$',
    r'(^|/)yarn\.lock$',
    r'(^|/)go\.mod$',
    r'(^|/)\.gitignore$',
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
IRON_LAW_PATTERN = re.compile(r'^\s*#+.*铁律', re.MULTILINE)
WORKLOG_FILE = "WORKLOG.md"

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
    if step_name not in ("1", "接需求", "入口"):
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
    return 0 if ok == checks else 0  # pre-step 只警告不阻断


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
    
    print(f"[enforce] ✓ WORKLOG 已记录步骤 {step_name}")
    return 0


def cmd_check_write(filepath: str) -> int:
    """写文件门禁：铁律5 红黄区保护"""
    path = _abs_path(filepath)
    rel = _relative_to_root(path)
    
    if not os.path.exists(path):
        pass  # 新建文件不检查
    
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
    
    # 检查铁律数量是否被删减（至少应有 9 条 铁律 N. 标记）
    law_count = len(re.findall(r'^\d+\.', content, re.MULTILINE))
    if law_count < 9:
        print(f"[enforce] ✗ 铁律9 违例：{rel} 仅有 {law_count} 条铁律（应有 ≥9 条）")
        print(f"[enforce]   铁律不可被删除或缩减")
        return 1
    
    print(f"[enforce] ✓ {rel} 铁律完整（{law_count} 条）")
    return 0


def cmd_check_evidence(exit_code_str: str, msg: str = "") -> int:
    """判定依据验证：铁律1 — 判定必须基于命令输出"""
    try:
        code = int(exit_code_str)
    except ValueError:
        print(f"[enforce] ✗ 铁律1 违例：exit_code 应为整数，收到 '{exit_code_str}'")
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
    
    # 4. enforce.py 自身存在（自检）
    print(f"[enforce] ✓ scripts/enforce.py 在运行")
    
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
