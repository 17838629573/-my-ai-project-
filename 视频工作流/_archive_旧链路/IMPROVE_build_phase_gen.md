# WHY build_phase_gen   (结构化·禁散文)

meta: tier=BUILD/phase | 136行 | 上游7 下游2

## basis 依据（搜证值/公式出处；改常数前必看）
- 【已修】帧数 = round(物理周期 × 素材采样帧率)，禁硬编码 30（铁律29）

## trap 坑（勿回退 / 已修 / 冲突）
- 【已修】帧数 = round(物理周期 × 素材采样帧率)，禁硬编码 30（铁律29）
- 禁线性爬升（旧实现 y 是相位的一次函数，首尾不闭合、第1帧还额外跳 0.5A）。
- 【已修】冠幅/肩高等次尺寸原一律取 real_m，导致冠幅=树高。
- 优先读 spec 显式声明的槽位，无声明才回退 real_m。
- 网格容量必须 >= 帧数：ceil(sqrt(n)) 方阵，禁写死 5x6/6x6
- 网格容量 >= 帧数：ceil(sqrt(n)) 方阵，禁写死 5x6/6x6

## intent 意图（为何存在）
出片前置：生图任务包 + 生图顺序队列。

## impact 改动影响（改本模块须回头验）
- 直接下游: build_video, run_gen_queue
- 验证命令: python3 impact.py build_phase_gen
