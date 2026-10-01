#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工作流文档脱敏工具（通用模板版）
--------------------------------
把绑定真实目标的侦察细节抽象为占位符，使方法论可公开复用，
而不构成对具体站点的攻击指引。

用法：
    python3 anonymize.py              # 演练，只列出会被改动的文件
    python3 anonymize.py --apply      # 实际改写，原件备份到 backup_raw/

使用前必做：
    把下面 RULES / CODE_RULES 里的「示例值」替换成你自己的目标映射。
    本文件内的域名、厂商名、长度基线、版本串均为虚构示例，
    直接照跑不会命中任何真实资产。
"""
import os, re, sys, shutil

# ---- 替换规则：长匹配在前 ----
# 左列 = 你要脱敏的真实字符串（正则）
# 右列 = 想展示的占位符
RULES = [
    # 域名 / 资产（示例：把 example.edu.cn 换成你的目标域）
    (r'www\.example\.edu\.cn',        '<TARGET-WWW>'),
    (r'www2\.example\.edu\.cn',       '<TARGET-WWW2>'),
    (r'news\.example\.edu\.cn',       '<TARGET-NEWS>'),
    (r'jwmis\.example\.edu\.cn',      '<TARGET-JW·教务>'),
    (r'authserver\.example\.edu\.cn', '<TARGET-CAS·认证>'),
    (r'my\.example\.edu\.cn',         '<TARGET-PORTAL·门户>'),
    (r'jyxx\.example\.edu\.cn',       '<TARGET-JY·就业>'),
    (r'mail\.example\.edu\.cn',       '<TARGET-MAIL>'),
    (r'vpn\.example\.edu\.cn',        '<TARGET-VPN>'),
    (r'example\.edu\.cn',             '<TARGET-APEX>'),

    # 第三方 SaaS / 参照站点（示例）
    (r'cdn\.vendor-saas\.com',        '<VENDOR-SaaS-CDN>'),
    (r'api\.vendor-saas\.com',        '<VENDOR-SaaS-API>'),
    (r'src\.ref-univ\.edu\.cn',       '<REF-SRC-PLATFORM>'),
    (r'www\.ref-univ\.edu\.cn',       '<REF-EDU-A>'),

    # 厂商 / 产品（去品牌，保留角色）
    (r'VENDOR-A-CAMPUS',              '<厂商A·教务系统>'),
    (r'VENDOR-A',                     '<厂商A>'),
    (r'VENDOR-B-CMS',                 '<厂商B·站群>'),
    (r'VENDOR-C-IDS',                 '<厂商C·统一认证>'),
    (r'CustomAppServer',              '<定制容器名>'),
    (r'SiteBuilder 9',                '<站群产品>'),
    (r'\bSB9\b',                      '<站群产品>'),

    # 应用根路径与自述路径（示例）
    (r'/app-root/',                   '<APPROOT>/'),
    (r'Calendar\.jsp',                '<自述路径·校历>'),
    (r'Timetable\.jsp',               '<自述路径·作息>'),
    (r'Notice\.jsp',                  '<自述路径·公告>'),
    (r'room-status\.html',            '<自述路径·教室状态>'),
    (r'score-query\.html',            '<自述路径·成绩/准考证>'),
    (r'schedule\.(course|room|class)\.html', r'<自述路径·课表\1>'),
    (r'frame/version\.html',          '<自述路径·运行环境指南>'),
    (r'LoginPage\.jsp',                '<登录入口页>'),
    (r'/cas/login\b',                 '/<CAS入口>'),
    (r'j_security_check',             '<容器原生表单认证端点>'),

    # 目标特定指纹值：长度基线 / md5 / ID（示例基线值，需替换）
    (r'\b(1200|2400|900|500|600|1900|2000|1300|2300)B\b', r'<LEN-\1>'),
    (r'\b[0-9a-f]{32}\b',             '<MD5>'),
    (r'\b10000\d{5}\b',               '<OWNER-ID>'),
    (r'\b(10001|20002|30003)\b',      '<ID>'),

    # 目标实例版本串（示例，需替换）
    (r'9\.0\.77',                     '<版本串·示例>'),
    (r'7\.0\.x',                      '<版本族·EOL>'),
]

# 标题里的目标名也清掉（示例）
TITLE_RULES = [
    (r'[（(]?example[）)]?', '<TARGET>'),
]

TARGET_EXT = ('.md', '.py', '.json', '.sh', '.csv', '.txt')
SKIP_DIR = {'__pycache__', '.git', 'backup_raw', 'oss', 'tmpout'}

# 代码文件专用：保持可执行，只换成虚构值
CODE_RULES = [
    (r'9\.0\.77',  '9.0.99'),      # 虚构版本，逻辑可跑但不可定位真实资产
    (r'7\.0\.x',   '7.0.99'),
    (r'\b10000\d{5}\b', '1000000001'),
    (r'\b(10001|20002|30003)\b', '10001'),
]

# 自身不参与脱敏，避免把映射表本身改坏
SELF_EXCLUDE = ('anonymize.py',)


def anonymize_text(t: str, is_code: bool = False) -> str:
    rules = (CODE_RULES + RULES) if is_code else RULES
    for pat, rep in rules:
        t = re.sub(pat, rep, t)
    return t


def main():
    apply = '--apply' in sys.argv
    os.makedirs('backup_raw', exist_ok=True)
    changed = []
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in SKIP_DIR]
        for f in sorted(files):
            if not f.endswith(TARGET_EXT) or f in SELF_EXCLUDE:
                continue
            p = os.path.join(root, f)
            raw = open(p, encoding='utf-8', errors='ignore').read()
            new = anonymize_text(raw, is_code=f.endswith('.py'))
            if new == raw:
                continue
            changed.append(p)
            if apply:
                shutil.copy2(p, os.path.join('backup_raw', f))
                open(p, 'w', encoding='utf-8').write(new)
    print(f"{'APPLIED' if apply else 'DRY-RUN'}  ->  {len(changed)} files")
    for p in changed:
        print('  ', p)


if __name__ == '__main__':
    main()
