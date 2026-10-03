#!/usr/bin/env python
"""deps_sync.py — 从源码 import 自动反推 deps.md 依赖侧（铁律：禁止手填依赖）

用法: python deps_sync.py [--write]
原理: AST 扫描每个模块的 import，过滤外部库，只留本项目模块。
     破环规则见 BREAK（硬编码最小集，须附理由）。
"""
import ast, os, re, sys

EXTERNAL = {'os','sys','json','math','numpy','np','cv2','re','time','random',
            'collections','itertools','functools','typing','dataclasses','pathlib',
            'subprocess','shutil','glob','abc','enum','copy','csv','struct'}
# 破环：solver_check 不得依赖 solver（否则 solver->solver_check->solver 成环）
BREAK = {('solver_check','solver')}

def scan(path):
    try:
        t = ast.parse(open(path,encoding='utf-8').read())
    except Exception:
        return set()
    out=set()
    for n in ast.walk(t):
        if isinstance(n, ast.Import):
            for a in n.names: out.add(a.name.split('.')[0])
        elif isinstance(n, ast.ImportFrom):
            if n.module and n.level==0: out.add(n.module.split('.')[0])
            # from . import x 相对导入跳过
    return out

def local_modules(root='.'):
    return {f[:-3] for f in os.listdir(root)
            if f.endswith('.py') and not f.startswith('__')}

def build(root='.'):
    mods = local_modules(root)
    deps={}
    for m in sorted(mods):
        p=os.path.join(root,m+'.py')
        imps=scan(p)
        d = sorted(i for i in imps if i in mods and i!=m and (m,i) not in BREAK)
        deps[m]=d
    return deps

CORE = {'build_video','enforce','run_batch','deps_sync','solver','solver_check',
        'systems','composite','chroma','framerate','driver','water'}

def has_selfcheck(m):
    try:
        src=open(m+'.py',encoding='utf-8').read()
    except Exception:
        return False
    return ('def self_check' in src) or ('self_check()' in src)

def topo(deps):
    """按依赖深度拓扑分层：无依赖 L0，依赖 L0 的 L1 ..."""
    depth={}
    for _ in range(12):                      # 迭代至收敛（有环时靠 BREAK 已破）
        ch=False
        for m in deps:
            d=0
            for x in deps[m]:
                if x in depth: d=max(d, depth[x]+1)
            if depth.get(m)!=d: depth[m]=d; ch=True
        if not ch: break
    return {m: min(d,3) for m,d in depth.items()}

def render(deps):
    lv=topo(deps)
    act={m for m in deps if has_selfcheck(m) or m in CORE}
    bucket={}
    for m in sorted(deps):
        bucket.setdefault('X' if m not in act else f'L{lv[m]}', []).append(m)
    title={'L0':'L0 原子层（无本项目依赖）','L1':'L1 计算层','L2':'L2 规划层',
           'L3':'L3 渲染/编排层','X':'X 休眠层（一次性脚本/归档/无自检）'}
    lines=['# deps.md — 模块依赖登记表',
           '# 由 deps_sync.py 自动从源码 import 反推 + 拓扑分层，禁止手填',
           '# 改了任何 import 后重跑: python deps_sync.py --write','']
    for k in ('L0','L1','L2','L3','X'):
        if k not in bucket: continue
        lines.append(f'# {k} {title[k]}')
        for m in bucket[k]:
            d=deps[m]
            lines.append(f"{m} -> {', '.join(d) if d else '(无)'}")
        lines.append('')
    return '\n'.join(lines)+'\n'

    for m in sorted(deps):
        d=deps[m]
        lines.append(f"{m} -> {', '.join(d) if d else '(无)'}")
    return '\n'.join(lines)+'\n'

if __name__=='__main__':
    deps=build('.')
    txt=render(deps)
    if '--write' in sys.argv:
        open('deps.md','w',encoding='utf-8').write(txt)
        print(f'deps.md 已由源码反推重写，{len(deps)} 个模块')
    else:
        print(txt)
