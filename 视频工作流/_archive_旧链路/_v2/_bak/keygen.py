# -*- coding: utf-8 -*-
"""keygen —— 整图关键帧的生图提示词。

新逻辑：整张图一次性生成（背景+人+树+旗全在里面），不做分层合成。
所以提示词的重点是「锁死背景 + 只描述动作相位」。

业界依据（可灵/即梦/Veo 实践一致）：
  1. 背景描述单独成句、必须前置
  2. 删除「飘动 / 渐变 / 闪烁 / 浮动」这类词 ——
     它们是每帧重绘的导火索，是闪烁开关不是氛围感
  3. 背景含具体物体时追加硬约束：
     「位置、尺寸、朝向、明暗分布全程保持完全一致于所有帧」
  4. 全局指令：全帧背景严格一致，禁止任何背景像素级变动

人物动作：
  用步态相位（0~1）描述，而不是像素坐标。
  相位由 spec 给出，物理可算，不靠猜。
"""
from __future__ import annotations

import spec

# ---------- 背景锁死模板 ----------
BG_LOCK_PREFIX = (
    "【背景严格锁定】{bg}。"
    "背景的位置、尺寸、朝向、明暗分布、材质纹理在全部帧中保持像素级完全一致。"
)

BG_FORBIDDEN = ("飘动", "渐变", "闪烁", "浮动", "流动", "摇曳", "变幻",
                "光影随风", "随风", "微光")

GLOBAL_LOCK = "全帧背景严格一致，禁止任何背景像素级变动。相机固定不动。"


def clean_bg(bg_desc: str) -> str:
    """剔除会触发每帧重绘的词汇。"""
    out = bg_desc
    for w in BG_FORBIDDEN:
        out = out.replace(w, "")
    return out.strip()


def bg_block(bg_desc: str) -> str:
    """背景块：必须前置，且已清洗禁用词。"""
    return BG_LOCK_PREFIX.format(bg=clean_bg(bg_desc)) + GLOBAL_LOCK


# ---------- 动作相位 ----------
def phase_desc(phase: float, subject: str = "僧人") -> str:
    """把一个步态相位(0~1)翻译成自然语言动作描述。

    相位 0.00  左脚跟着地
    相位 0.25  左腿支撑，右腿前摆
    相位 0.50  右脚跟着地
    相位 0.75  右腿支撑，左腿前摆
    """
    p = phase % 1.0
    tbl = [
        (0.125, "左脚跟刚着地，右腿在后蹬地，双臂自然前后摆动"),
        (0.375, "左腿单腿支撑，身体略升，右腿向前摆动迈出"),
        (0.625, "右脚跟刚着地，左腿在后蹬地，双臂摆到反向"),
        (0.875, "右腿单腿支撑，身体略升，左腿向前摆动迈出"),
    ]
    for hi, d in tbl:
        if p < hi:
            return f"{subject}{d}"
    return f"{subject}左脚跟刚着地，右腿在后蹬地，双臂自然前后摆动"


def keyframe_prompt(bg_desc: str,
                    phase: float,
                    subject: str = "僧人",
                    extra: str = "") -> str:
    """组装一张关键帧的完整提示词。顺序固定：背景 → 动作 → 补充。"""
    parts = [bg_block(bg_desc), phase_desc(phase, subject)]
    if extra:
        parts.append(extra)
    return "".join(parts)


def plan(bg_desc: str,
         n_keys: int | None = None,
         speed_mps: float = spec.DEFAULT_SPEED_MPS,
         subject: str = "僧人") -> dict:
    """生成一个完整周期的全部关键帧提示词。"""
    per = spec.period(speed_mps)
    n = spec.keyframes(per, n_keys or spec.DEFAULT_KEYS_PER_CYCLE)
    iv = spec.key_interval(per, n)
    mul = spec.interp_mul(iv)
    prompts = []
    for i in range(n):
        # 相位均匀分布；最后一张回到 0 以便循环闭合
        ph = (i / n) % 1.0
        prompts.append({
            "index": i,
            "phase": round(ph, 4),
            "t": round(i * iv, 4),
            "prompt": keyframe_prompt(bg_desc, ph, subject),
        })
    return {
        "period_s": round(per, 4),
        "n_keys": n,
        "key_interval_s": round(iv, 4),
        "interp_mul": mul,
        "cycle_frames": spec.cycle_frames(per),
        "prompts": prompts,
    }


# ---------- 自检 ----------
def self_check() -> None:
    bg = "唐代城墙，夕阳侧逆光，青砖墙面有斑驳痕迹，远处有城楼剪影"

    # 1) 禁用词必须被清洗
    dirty = "窗帘飘动，墙面光影渐变闪烁，湖面浮动微光"
    c = clean_bg(dirty)
    for w in BG_FORBIDDEN:
        assert w not in c, f"禁用词未清除: {w} -> {c}"

    # 2) 背景块必须前置（提示词开头就是背景）
    pr = keyframe_prompt(bg, 0.25)
    assert pr.startswith("【背景严格锁定】"), pr[:40]
    assert "僧人" in pr

    # 3) 相位描述覆盖四个象限且不同
    ds = [phase_desc(p) for p in (0.0, 0.25, 0.5, 0.75)]
    assert len(set(ds)) == 4, f"相位描述重复: {ds}"
    for d in ds:
        assert "腿" in d, d

    # 4) plan 结构完整
    pl = plan(bg, 5)
    assert pl["n_keys"] == 5, pl["n_keys"]
    assert len(pl["prompts"]) == 5
    assert pl["prompts"][0]["phase"] == 0.0
    assert abs(pl["prompts"][1]["phase"] - 0.2) < 1e-6
    # 间隔不超过半周期（业界硬约束）
    assert pl["key_interval_s"] <= pl["period_s"] * 0.5 + 1e-9
    # 每张提示词都必须带背景锁
    for p in pl["prompts"]:
        assert p["prompt"].startswith("【背景严格锁定】")
        assert "飘动" not in p["prompt"]

    # 5) 插帧倍数 >= 1
    assert pl["interp_mul"] >= 1

    print("keygen self_check OK  period=%.3fs keys=%d 间隔=%.3fs 插%d帧/对"
          % (pl["period_s"], pl["n_keys"], pl["key_interval_s"],
             pl["interp_mul"]))


if __name__ == "__main__":
    self_check()
