"""链式参考图生成调度：上一批输出 = 下一批参考图
业界: AR-LDM 自回归后验 P(x_j | x̂_<j)
工具限制: 无 denoise 参数 -> seed 固定 + prompt 声明不变项
"""
import math, os

# 铁律100: 视频帧率目标(非游戏的8-16帧)
FPS_TARGET = 32
CELLS_PER_BATCH = 8          # 每批图集格数(4x2)
# 业界最佳重绘区间 0.25-0.35; 本工具不可设, 用等效手段
DENOISE_BEST = (0.25, 0.35)

def frames_for(period_s, fps=FPS_TARGET):
    """一周期应采样帧数(铁律100)"""
    n = max(1, int(round(period_s * fps)))
    return n

def batches_for(n, per=CELLS_PER_BATCH):
    """分批次, 每批 per 格"""
    return [(i, min(per, n - i)) for i in range(0, n, per)]

def chain_prompt(family, obj_desc, frame_ids, pose_desc, keep=()):
    """组装单批提示词. keep = 必须保持不变的项(画风/服饰/配色)"""
    keep_txt = "、".join(keep) or "人物外貌、服饰、配色、画风"
    return (
        f"{obj_desc}，{family}族序列帧图集，"
        f"共{len(frame_ids)}格 4行×2列均匀排列，"
        f"姿态依次为：{pose_desc}；"
        f"保持{keep_txt}与第一张图完全一致，只改变姿态；"
        f"纯色背景无渐变无文字无格线，每格主体完整居中"
    )

def self_check():
    ck = []
    def a(n, c): ck.append((n, bool(c)))
    a("32fps: 1.0s周期=32帧", frames_for(1.0) == 32)
    a("32fps: 2.273s周期=73帧", frames_for(2.273) == 73)
    a("批次覆盖 32->4批", len(batches_for(32)) == 4)
    a("批次不漏帧", sum(b for _, b in batches_for(32)) == 32)
    a("批次末批可不足", batches_for(35)[-1][1] == 3)
    a("重绘区间=业界0.25-0.35", DENOISE_BEST == (0.25, 0.35))
    p = chain_prompt("biped", "玄奘", list(range(8)), "左腿前伸")
    a("提示词含保持不变声明", "完全一致" in p)
    a("提示词含族", "biped" in p)
    # 证伪: 游戏8帧不达标
    a("证伪: 游戏8帧<32fps要求", frames_for(1.0) > 8)
    return ck
