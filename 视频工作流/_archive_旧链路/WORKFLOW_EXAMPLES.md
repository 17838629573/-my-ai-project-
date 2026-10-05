# BEGIN EXAMPLES / END EXAMPLES  ← 自检扫描时剔除这段
EXAMPLES = {
  "kind": { "人物": "玄奘 身高1.70m / 躯干=driven 发丝=passive 衣摆=passive 足=anchor / gait",
            "静物": "幡旗 0.90×0.30m / 幡杆=anchor 幡身=driven 垂带=passive / wind", ... },
  "role": { anchor/driven/passive 各 3 个跨类示例 },
  "source": { wind/gait/impulse/none },
  "family": { cantilever/chain/hinge/free_surface },
}
```

**关键**：示例里带具体物体名是**允许的、必需的**（心智模型）；
提问逻辑区出现具体物体名是**违规的**（自检第 21 项扫描，剔除示例区后判 NULL）。

### 铁律38：任务包必须写明「填到哪 / 填什么 / 跑什么」

AI 不只要知道填什么值，还要知道**落到哪个文件、跑哪条命令**。

```
填到哪个文件   scene_spec.json（本目录）
填什么        assemble() 输出的『组装』+ 补齐『待搜物性』每个槽位
跑什么命令     python3 solver.py --run scene_spec.json
跑完得到      每物体 regime/频率/周期/帧数 + 35相位骨架图集 _骨架/<name>N.png
然后AI做什么   拿骨架图集去图生图 → 序列帧 <name>_fNN.png → 交回代码播放
交回格式      帧数须等于 solver.frames，±15% 内钳制，超出报错（铁律30）
```

HOWTO 已内置为常量，自检第 25 项验证其包含 file/what/cmd 三要素。

### 状态判定（机器可判，已修正）
```
绿 = 有契约 + 有 self_check + 自检PASS + 输出≥30字符
黄 = 有契约 + 有 self_check + 自检PASS（输出短）
红 = 无契约 / 无 self_check / 自检FAIL      → 门禁应拦截
```
**当前活跃层真·绿 = 6/16**（photo_rules, skeleton_runtime, motion_lib, actors, physics_rules, environment, character_sheet, physics 中有 self_check 的）

### 修复进度
- render_v4 ✅ 已补 self_check（5 项：三轴/背景/actors门禁/build_engine/输出名）
  - 自检立刻抓出 2 个真 bug：镜7→8 同景别同角度跳切（一直只警告不阻断）
    、默认输出名是历史成片名（铁律19）→ 均已修，现 5 项全 PASS
  - 契约标黄；`python3 render_v4.py` 默认自检（0.2s），`--render` 才真渲染
- 待补：chroma, subtitle, systems, loop_engine, film_assemble（5 个）
- systems ✅ 已补 self_check（6 项：无内联物理/无魔法系数/步速/起伏/冒烟/Verlet收敛）
  - 自检立刻抓出 2 个静默 bug：
    · 气动力 `*1e-3` 量纲补丁（铁律14）
    · **相对速度漏 px/s->m/s 换算，气动力大 px_per_m^2 = 16.5 万倍 -> Verlet nan**
      （这个 bug 一直存在，被 1e-3 压着没暴露；去掉魔法系数后才显形）
  - 修后 Verlet 收敛：残余速度 5.0000 -> 0.0000
- 待补：chroma, subtitle, loop_engine, film_assemble（4 个）
  → **全部补完**（各抓出 1 个真 bug：loop_engine 注册不清缓存致新系统永不执行、
    film_assemble fps=60 写死、chroma 返回二元组调用方未解包、
    subtitle check_timing 写死 24fps 而输出 60fps→时长判据错位 2.5 倍）
  → **NO_SELFTEST 归零，活跃 16 模块全 PASS**
  → 另发现 2 项自检自身假 PASS（永远成立的空检查），已改成对照实验
