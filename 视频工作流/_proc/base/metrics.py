#   契约: base/metrics
#   一句话: 判据测量公式库（最底层，任何层都可引用）
#   完整契约见 base/__init__.py
#   依据: 分层契约规定 tools 在 tests 之上（tests 不得 import tools），
#         而打滑占比等公式要被 tests 用来产生判据值；公式无工具属性、
#         无副作用，属基础设施，下沉 base 后 tests 与 tools 均可引用。
#   输入: 关节帧序列 + 足关节名 + 接触序列 + 竖直轴
#   输出: 测量值（float / dict）
#   依赖: 无（纯函数，不 import 项目内任何模块）
#   约束: 只测量不拍阈值 —— 阈值一律登记在 harness.CRIT，守 A1 铁律；
#         up_axis 必须显式传入，禁止假设坐标轴方向。
#   校验: python _proc/tools/batchgate.py
# -*- coding: utf-8 -*-
"""度量公式（最底层，任何层都可引用）。

把 foot_skate_ratio 从 tools/measure/motionqual 下沉到 base 的原因：
它是**判据测量公式**，tests 要用它产生判据值，而分层契约规定 tools 在 tests
之上（tests 不得 import tools）。公式本身无工具属性、无副作用，属基础设施，
放在 base 后 tests 与 tools 均可引用，分层自然合规。

出处与口径说明随函数一并搬来，未作删改。
"""
import math


def _is_contact_frame(frames, i, foot_joints, contact_seq, contact_thresh, up_axis):
    """第 i 帧是否接触帧。显式给了 contact_seq 就以它为准，否则按足端高度判。"""
    if contact_seq is not None:
        return i < len(contact_seq) and bool(contact_seq[i])
    return not all(frames[i][j][up_axis] > contact_thresh for j in foot_joints)


def _frame_has_skate(frames, i, foot_joints, horiz, thresh_m):
    """第 i 帧相对 i-1 帧是否存在足端水平滑移超阈。"""
    for j in foot_joints:
        if j not in frames[i] or j not in frames[i - 1]:
            continue
        dx = frames[i][j][horiz[0]] - frames[i - 1][j][horiz[0]]
        dz = frames[i][j][horiz[1]] - frames[i - 1][j][horiz[1]]
        if math.sqrt(dx * dx + dz * dz) > thresh_m:
            return True
    return False


def foot_skate_ratio(frames, foot_joints, contact_seq=None,
                     thresh_m=0.01, contact_thresh=0.02, up_axis=2):
    """打滑帧占比：业界按 ratio 报告，而不是只报均值。

    出处: Motion Toolbox evaluation config —— foot_skating_joint 按 ratio 评估，
         good < 0.40，moderate < 0.60（越小越好）。
         与其均值口径（我们的 skate_cm_frame）互补：均值会被少数极端帧拉偏，
         占比能回答"有多少帧在滑"，业界主流按占比报告。

    口径: 分母取**接触帧**（与 CHOIS 的 contact-based 定义一致：只在
         足端贴地期间才谈得上打滑）。位移取**世界坐标**下的足端水平位移——
         必须相对地面，不能相对身体（相对身体会把"整体前进"误判成滑步，
         我们此前在四足步态上踩过这个坑）。
         thresh_m 为单帧打滑判定阈值，取项目现役 skate_cm_frame=1.0cm/frame；
         注意该值经锚点比对被标为动捕真值(0.10cm/frame)的 10 倍，属偏离项，
         故本函数只用它做"单帧是否打滑"的口径，占比阈值 0.40 才是外部来源。

    返回: (ratio, n_contact, n_skate)；无接触帧时 ratio 为 None（不是 0.0——
          0.0 会被误读成"零打滑"，实际是"没得测"）。

    up_axis（关键，显式声明）: 竖直轴下标。本模块内部（zmp_series/_demo_frames）
          约定 (x, y, z) 中 **z 为上**，故默认 up_axis=2。但项目内另有
          (x=前进, h=高度, z=侧向) 的世界坐标约定（tests/common._world），
          那里竖直轴是 index 1。两处口径不一致，必须显式传参，禁止靠猜——
          猜错会把"抬脚高度变化"当成水平滑移（我们此前在混合场景里因坐标口径
          不一致踩过 NaN 污染，属同类病）。
    """
    n = len(frames)
    if n < 2:
        return (None, 0, 0)
    horiz = [a for a in (0, 1, 2) if a != up_axis]
    n_contact = 0
    n_skate = 0
    for i in range(1, n):
        if not _is_contact_frame(frames, i, foot_joints, contact_seq,
                                 contact_thresh, up_axis):
            continue
        n_contact += 1
        if _frame_has_skate(frames, i, foot_joints, horiz, thresh_m):
            n_skate += 1
    if n_contact == 0:
        return (None, 0, 0)
    return (n_skate / float(n_contact), n_contact, n_skate)


def amp_ratio(amp_pp_m, body_len_m):
    """振幅比 A* = A / L。

    出处: Saadat et al. 2017《On the rules for aquatic locomotion》
         PhysRevFluids 2, 083102：St 单独不足以判定高效游动，需附加 A* ∈ [0.1, 0.3]。
         论文原文 "A* (=A/L)"，与 "St(=fA/U)" 共用同一个 A。

    口径（关键，已核实）: 该 A 是**峰峰振幅** A_p-p，不是单边振幅。
         Arellano《Biomechanics and Medicine in Swimming》: "St = A_p-p·f/U, where
         A_p-p is the tail-beat peak-to-peak amplitude"；
         机器人鱼文献同口径: "A is peak-to-peak stroke amplitude of the tail tip"。
         中文报道亦为"来回摆动的距离"在体长 1/10~3/10 之间，即峰峰。
         —— 若误用单边振幅，A* 会小一半，判据口径即错。

    参数: amp_pp_m 尾端峰峰振幅（米）；单边振幅请先乘 2。
    """
    if body_len_m <= 0:
        return None
    return amp_pp_m / body_len_m
