# 契约: proc/showreel
#   一句话: 90 秒连续长镜头总包：连续相机 + 全局扰动 + 赛博朋克物理世界 + 时间线
"""showreel —— 90 秒不切镜长镜头。

小模块（依赖单向，自上而下）:
  params.py   全局连续扰动（g/μ/风/e/质量/timeScale/震动），全为 t 的纯函数
  camrig.py   连续运镜（跟随/横移/推拉/低角度/俯拍/微距），C1 连续
  scene.py    赛博朋克街道物理世界（多米诺/堆/斜坡/摆锤/墙/梯子/靶/绳/铰链门）
  timeline.py 90 秒时间线编排与出片（本包的主入口）

依赖: motion(character/camera/rigid2d/run), scene.kit, shape, color
被依赖: 无
约束: 物理仿真与渲染帧率解耦（踩过坑：仿真步数当帧数→慢放12倍）;
      参数扰动一律走 GlobalParams 纯函数，禁止逐帧随机（随机=抖动）
校验: python3 -m showreel.scene
"""
