#!/usr/bin/env python3
"""门禁自检：每个用例断言『必须被阻断』。AI 改完 enforce.py 后必跑。"""
import os, re, subprocess, shutil, tempfile, sys

SRC = sys.argv[1] if len(sys.argv)>1 else "repo"
E = "python3 scripts/enforce.py"

def setup():
    d = tempfile.mkdtemp()
    shutil.copytree(SRC, d+"/p", dirs_exist_ok=True)
    return d+"/p"

def run(cwd, cmd):
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    return r.returncode

def _patch_iron(c):
    p=c+'/WORKFLOW.md'
    t=open(p,encoding='utf-8').read()
    # 把第1条铁律正文整行换成反面内容（保留标题与编号，专测"改内容不改标题"）
    t2=re.sub(r'^1\..*$', '1. 判定可凭经验估计，无需每次跑命令。', t, flags=re.M)
    assert t2!=t, "替换未生效"
    with open(p,'w',encoding='utf-8') as f: f.write(t2)
    return run(c, f'{E} check-iron-law WORKFLOW.md')

CASES = [
 ("红区无授权写入",       lambda c: run(c, f'{E} check-write .env')),
 ("授权文件缺失",         lambda c: run(c, f'{E} check-auth nonexistent')),
 ("授权已过期",           lambda c: (os.makedirs(c+'/tracks',exist_ok=True),
                                    open(c+'/tracks/x.track.md','w').write('问: a\n授权: 临时\n到期日: 2020-01-01\n'),
                                    run(c, f'{E} check-auth x'))[-1]),
 ("授权缺到期日字段",     lambda c: (os.makedirs(c+'/tracks',exist_ok=True),
                                    open(c+'/tracks/y.track.md','w').write('问: a\n授权: 临时\n'),
                                    run(c, f'{E} check-auth y'))[-1]),
 ("WORKLOG 无记录过门",   lambda c: run(c, f'{E} gate post-step 1')),
 ("check-evidence 非整数", lambda c: run(c, f'{E} check-evidence 应该没问题')),
 # ↓ 以下四条是「AI 改脚本时最容易悄悄放水」的地方
 ("铁律内容被替换",       lambda c: _patch_iron(c)),
 ("check-evidence 传失败退出码", lambda c: run(c, f'{E} check-evidence 1 "测试挂了3个"')),
 ("WORKLOG 写入失败记录",  lambda c: (open(c+'/WORKLOG.md','w').write(
                            '2026-09-29 | 步骤5 | 测试失败,卡住\n'),
                            run(c, f'{E} gate post-step 5'))[-1]),
 ("AI 自造永久授权",      lambda c: (os.makedirs(c+'/tracks',exist_ok=True),
                                    run(c, f'{E} check-write tracks/.env.track.md'))[-1]),
]

def _tr(c, name, body):
    os.makedirs(c+'/tracks',exist_ok=True)
    open(c+f'/tracks/{name}.track.md','w').write(body)

CASES += [
 ("核心区无授权改 enforce.py", lambda c: run(c, f'{E} check-write scripts/enforce.py')),
 ("核心区长期授权(次数:3)", lambda c: (_tr(c,'scripts_enforce.py','问: x\n授权: 长期\n次数: 3\n到期日: -\n'),
                                    run(c, f'{E} check-write scripts/enforce.py'))[-1]),
 ("核心区改 skills/*/SKILL.md", lambda c: run(c, f'{E} check-write skills/write/SKILL.md')),
 ("核心区改 WORKFLOW.md", lambda c: run(c, f'{E} check-write WORKFLOW.md')),
]

CASES += [
 ("篡改留痕 CORELOG.md", lambda c: run(c, f'{E} check-write CORELOG.md')),
 ("篡改基线 .workflow-baseline", lambda c: run(c, f'{E} check-write .workflow-baseline/scripts/enforce.py')),
]

def _final(c):
    """信任升级专项：10次有效→L2, 半永久+5次→L3"""
    shutil.copytree(SRC, c, dirs_exist_ok=True)
    import subprocess as sp
    def r(cmd): return sp.run(cmd, shell=True, cwd=c, capture_output=True, text=True).returncode
    ok = True
    # L1: 永久授权应被拒
    os.makedirs(c+'/tracks',exist_ok=True)
    open(c+'/tracks/scripts_enforce.py.track.md','w').write('问: x\n答: 永久\n有效期: 永久\n到期日: -\n')
    ok &= (r(f'{E} check-write scripts/enforce.py') != 0)
    # 10 次有效
    for i in range(10):
        r(f'{E} log-effect scripts/enforce.py 有效 10/14 第{i}次')
    open(c+'/tracks/scripts_enforce.py.track.md','w').write('问: x\n答: 半永久\n有效期: 半永久\n到期日: 2026-12-28\n')
    ok &= (r(f'{E} check-write scripts/enforce.py') == 0)   # L2 应放行半永久
    # L2 申请永久应被拒
    open(c+'/tracks/scripts_enforce.py.track.md','w').write('问: x\n答: 永久\n有效期: 永久\n到期日: -\n')
    ok &= (r(f'{E} check-write scripts/enforce.py') != 0)
    # 半永久启用 + 5 次有效 → L3
    open(c+'/tracks/scripts_enforce.py.track.md','w').write('问: x\n答: 半永久\n有效期: 半永久\n到期日: 2026-12-28\n')
    r(f'{E} check-write scripts/enforce.py')
    for i in range(5):
        r(f'{E} log-effect scripts/enforce.py 有效 12/14 半永久期{i}')
    open(c+'/tracks/scripts_enforce.py.track.md','w').write('问: x\n答: 永久\n有效期: 永久\n到期日: -\n')
    ok &= (r(f'{E} check-write scripts/enforce.py') == 0)   # L3 应放行永久
    return 0 if ok else -1

d = tempfile.mkdtemp()+"/p"
try:
    res = _final(d)
finally:
    shutil.rmtree(d, ignore_errors=True)
print("\n信任升级专项（L1→L2→L3 跃迁与拦截）")
print("  " + ("✓ 全程符合预期" if res == 0 else "✗ 异常"))

print(f"门禁自检（被测: {SRC}）— 每条期望 exit≠0（阻断）\n" + "-"*52)
passed = 0
for name, fn in CASES:
    cwd = setup()
    try: code = fn(cwd)
    except Exception as e: code = -99
    ok = code != 0
    passed += ok
    print(f"  {'✓ 阻断' if ok else '✗ 放行(缺陷)':<14} exit={code:<3} {name}")
    shutil.rmtree(cwd, ignore_errors=True)
print("-"*52)
print(f"通过 {passed}/{len(CASES)}")
