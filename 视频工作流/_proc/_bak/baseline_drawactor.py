"""draw_actor 拆分前的行为基准：6 组配置 × 每帧 md5。

用途：重构（Extract Method）前后各跑一次，md5 必须完全一致。
      行为变了就不叫重构，叫 bug。
出处：Fowler / SourceMaking Extract Method — "重构不改变行为"。
"""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motion import run as R
from motion import camera
from motion import character as C

# 6 组对照：覆盖朝向 / 模板 / 描边三个维度
CONFIGS = [
    ("侧走_humanoid_描边", dict(yaw=90.0, template="humanoid"), True),
    ("正面_humanoid_描边", dict(yaw=180.0, template="humanoid"), True),
    ("背面_humanoid_描边", dict(yaw=0.0, template="humanoid"), True),
    ("斜45_humanoid_描边", dict(yaw=45.0, template="humanoid"), True),
    ("侧走_humanoid_无描边", dict(yaw=90.0, template="humanoid"), False),
    ("侧走_quadruped_描边", dict(yaw=90.0, template="quadruped"), True),
]
TS = [0.0, 0.37, 0.74, 1.11]


def main():
    out = {}
    here = os.path.dirname(os.path.abspath(__file__))
    imgdir = os.path.join(here, "基准帧")
    os.makedirs(imgdir, exist_ok=True)

    for name, kw, stroke in CONFIGS:
        cam = camera.OrthoCam(s=960 * 0.168, cx=540 / 2, y0=960 * 0.86)
        hs = []
        for t in TS:
            img = R.frame(t, yaw=kw["yaw"], template=kw["template"], cam=cam)
            # 若需对比无描边，走 draw_actor 直接调用
            if not stroke:
                GP = C.gait_params("natural")
                d = 0.67 * t
                ph = (d / (GP["stride"] * 1.70) / 2.0) % 1.0
                J = C.gait(ph, "natural")
                cv2_ = R.CV(540, 960)
                R.draw_actor(cv2_, cam, J, Xc=0.0, Zc=6.0, yaw=kw["yaw"],
                             body_h=1.70, template=kw["template"], stroke=False)
                img = cv2_.img
            a = __import__("numpy").asarray(img, dtype="uint8")
            hs.append(hashlib.md5(a.tobytes()).hexdigest())
            img.save(os.path.join(imgdir, f"{name}_t{t:.2f}.png"))
        out[name] = hs
        print(f"{name:24s} {hs[0][:12]}...")

    p = os.path.join(here, "基准_drawactor.json")
    with open(p, "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print("saved", p)


if __name__ == "__main__":
    main()
