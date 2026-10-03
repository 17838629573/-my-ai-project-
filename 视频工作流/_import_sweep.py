#!/usr/bin/env python3
"""全量导入体检：静默 import 所有活跃模块，报告失败。"""
import os, importlib, sys, io, contextlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.dirname(os.path.abspath(__file__))
SKIP = ('_audit', '_actor', '_extract', '_split', '_build32',
        'gate_', 'deps_sync', 'run_batch')

bad, n = [], 0
for f in sorted(os.listdir(BASE)):
    if not f.endswith('.py') or f.startswith('_archive'):
        continue
    m = f[:-3]
    if m.startswith(SKIP):
        continue
    n += 1
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            importlib.import_module(m)
    except BaseException as e:
        bad.append((m, type(e).__name__, str(e)[:70]))

print('导入体检: %d 个模块, 失败 %d' % (n, len(bad)))
for b in bad[:12]:
    print('  FAIL', b[0], '|', b[1], '|', b[2])
