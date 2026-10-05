"""补契约块 + 把逆向依赖的 character.py 归位到 motion 层。"""
import os
import shutil

ROOT = os.path.dirname(os.path.abspath(__file__))

# 一句话职责（契约块插到文件最顶部）
ONE = {
    ("color", "paint.py"): "按胶囊 region 查色卡，配合 SDF 法线做明暗着色；颜色挂 region 不挂像素",
    ("motion", "beat.py"): "节拍时间线：prep→stroke→relax 三相位串多段动作，含跨段无跳变与互斥校验",
    ("motion", "camera.py"): "相机：视高/焦距/px_per_m(Z)/反投影；人物与路必须共用同一台",
    ("motion", "run.py"): "时间线与出片：逐帧渲染并写 mp4",
    ("motion", "stage.py"): "场景合成：烘焙背景 + 人物 + 出片",
    ("motion", "wind.py"): "风场：主弯曲 + 细节弯曲，相位纳入世界坐标使异株不同步",
    ("motion", "character.py"): "【超标·冻结封存·待下沉】旧人物渲染，依赖相机与背景，故归 motion 层",
    ("scene", "bgpack.py"): "背景包：五种配方的参数表与展开，输出 geom 供人物对齐",
    ("scene", "detail.py"): "近处细节：草叶/窗户/叶簇/远处行人，按 LOD 分级",
    ("scene", "kit.py"): "元件库：天空/云/山/树/草/花/城/路；路把几何写进 ctx 供房子避让",
    ("shape", "line.py"): "骨架模板 → 胶囊形体(带 region) → SDF → 轮廓线与细节线",
    ("(root)", "formula.py"): "公式注册表与 STUB 门禁：缺公式抛错并给搜索关键词，禁止凭记忆写近似值",
    ("(root)", "prompt2spec.py"): "提示词 → 规格对照：逐字段判能做/降级/不能，STUB 带搜索提示",
    ("(root)", "beat_demo.py"): "入口脚本：走 beat 时间线出演示片",
}


def insert_contract(path, pkg, fn):
    one = ONE.get((pkg, fn))
    if not one:
        return False
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    if "契约:" in src:
        return False
    block = f'# 契约: proc/{pkg}/{fn[:-3]}\n#   一句话: {one}\n#   完整契约见 {pkg}/__init__.py\n'
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(block + src)
    return True


# 1) character.py 从 shape 归位到 motion（它依赖 camera/kit，属上层）
src_ch = os.path.join(ROOT, "shape", "character.py")
dst_ch = os.path.join(ROOT, "motion", "character.py")
if os.path.exists(src_ch):
    shutil.move(src_ch, dst_ch)
    print("归位 shape/character.py -> motion/character.py（消除逆向依赖）")
    # 同包内改为平级导入
    with open(dst_ch, encoding="utf-8") as fh:
        s = fh.read()
    s = s.replace("from motion import camera", "import camera")
    s = s.replace("from scene import kit", "from scene import kit")
    with open(dst_ch, "w", encoding="utf-8") as fh:
        fh.write(s)
    # 引用方改为同包导入
    for fn in ("run.py", "stage.py", "beat.py"):
        p = os.path.join(ROOT, "motion", fn)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as fh:
                s = fh.read()
            s = s.replace("from shape import character as C", "import character as C")
            s = s.replace("from shape import character", "import character")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(s)

# 2) 补契约块
n = 0
for dirpath, _, files in os.walk(ROOT):
    if "_bak" in dirpath or "__pycache__" in dirpath:
        continue
    for fn in sorted(files):
        if not fn.endswith(".py") or fn == "__init__.py":
            continue
        p = os.path.join(dirpath, fn)
        rel = os.path.relpath(p, ROOT)
        pkg = rel.split(os.sep)[0] if os.sep in rel else "(root)"
        if insert_contract(p, pkg, fn):
            n += 1
print("补契约", n, "个文件")
