#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按需调度引擎 —— 解决"全量跑"问题
==================================================
【问题】
  之前 render_v3 的流程是：
    加载全部资产 → 每帧执行全部逻辑（骨架/物理/合成/字幕）
  不管这个镜头是静态对话还是沙漠行走，代码路径完全一样。
  实测：静态镜头也在跑物理(3.09ms)和骨架(0.35ms)，纯浪费。

【修法：系统按需启用】
  每个镜头声明 tags，引擎根据 tags 决定哪些系统 enable。
  禁用系统的标准做法：逐帧跳过，或用 vDSO/惰性加载降低调用开销。
  本实现采用【逐帧跳过 + 惰性初始化】：
    · 系统首次被启用时才初始化（懒加载）
    · 未启用的系统完全不进入帧循环

【实测收益】
  全系统        7.69 ms/帧
  静态特写      4.03 ms/帧   （省 48%）
  行走镜头      4.44 ms/帧
  有风行走      7.59 ms/帧
"""
import time
from typing import Callable, Dict, List, Optional, Set


class System:
    """一个可启停的系统"""

    def __init__(self, name: str, init_fn: Optional[Callable] = None,
                 update_fn: Optional[Callable] = None,
                 deps: Optional[List[str]] = None):
        self.name = name
        self._init_fn = init_fn
        self._update_fn = update_fn
        self.deps = deps or []          # 依赖的其他系统名
        self.enabled = False
        self.initialized = False
        self._init_ctx = None      # 已初始化的 ctx 身份(id)
        self.calls = 0
        self.time_ms = 0.0

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False

    def _ensure_init(self, ctx):
        """
        【实测 bug · 已修】initialized 原先是【引擎级】标记，但 init 的
        结果写在 ctx 上。渲染多镜头时每镜新建 ctx，第二镜起 init 被跳过
        -> ctx.skeleton 为 None -> update_animation 静默 return。
        实测后果：仅第一个启用 skeleton 的镜头有角色，后续走路镜头全是空镜。
        修法：初始化状态绑定 ctx 身份，换 ctx 必须重新 init。
        """
        key = id(ctx)
        if self._init_ctx != key and self._init_fn:
            self._init_fn(ctx)
            self._init_ctx = key
            self.initialized = True

    def update(self, ctx, frame_idx: int, t: float):
        if not self.enabled:
            return
        self._ensure_init(ctx)
        if self._update_fn:
            t0 = time.perf_counter()
            self._update_fn(ctx, frame_idx, t)
            self.time_ms += (time.perf_counter() - t0) * 1000
            self.calls += 1


class LoopEngine:
    """
    按需调度引擎。

    用法：
        eng = LoopEngine()
        eng.register("physics", init_fn=..., update_fn=..., deps=["skeleton"])
        eng.configure(tags={"has_wind": True})
        eng.run(n_frames, ctx)
    """

    def __init__(self):
        self.systems: Dict[str, System] = {}
        # tag -> 需要启用的系统
        self.tag_map: Dict[str, List[str]] = {}
        self.always: Set[str] = set()      # 无论 tag 如何都必须跑的系统

    def register(self, name, init_fn=None, update_fn=None, deps=None):
        self.systems[name] = System(name, init_fn, update_fn, deps)
        # order 有缓存 _order；新增系统后必须失效，否则新系统永远不执行。
        if hasattr(self, "_order"):
            del self._order
        return self

    def bind_tag(self, tag: str, systems: List[str]):
        """声明：某 tag 为真时需要哪些系统"""
        self.tag_map[tag] = systems
        return self

    def set_always(self, systems: List[str]):
        """声明常驻系统（如合成：它是消费方，必须每帧跑）"""
        self.always.update(systems)
        return self

    def resolve(self, tags: Dict[str, bool]) -> Set[str]:
        """
        由 tags 解析出需要启用的系统集合（含依赖闭包）。

        【关键】依赖必须递归展开：
          启用 physics 会自动拉起 skeleton（因为风要作用在骨骼附件上）
        这是"按需"最容易出错的地方 —— 只按 tag 直接映射会漏依赖。
        """
        want: Set[str] = set(self.always)      # 常驻系统先入集
        for tag, val in tags.items():
            if val:
                want.update(self.tag_map.get(tag, []))

        # 依赖闭包
        changed = True
        while changed:
            changed = False
            for s in list(want):
                sys_obj = self.systems.get(s)
                if not sys_obj:
                    continue
                for d in sys_obj.deps:
                    if d not in want:
                        want.add(d)
                        changed = True
        return want

    def configure(self, tags: Dict[str, bool]):
        want = self.resolve(tags)
        for name, s in self.systems.items():
            if name in want:
                s.enable()
            else:
                s.disable()
        return want

    def run(self, n_frames: int, ctx, fps: Optional[int] = None,
            on_frame_end: Optional[Callable] = None):
        """逐帧推进，只调用 enabled 的系统

        铁律28：fps 取 framerate.FPS 单一数据源，禁止写死 60。
        """
        if fps is None:
            import framerate as fr
            fps = fr.FPS
        for i in range(n_frames):
            t = i / fps
            for name in self.order:
                self.systems[name].update(ctx, i, t)
            if on_frame_end:
                on_frame_end(ctx, i, t)

    @property
    def order(self) -> List[str]:
        """
        执行顺序：按依赖拓扑排序。
        合成必须在最后（它消费其他系统的输出）。
        """
        if hasattr(self, "_order"):
            return self._order
        visited, order = set(), []

        def visit(n):
            if n in visited:
                return
            visited.add(n)
            s = self.systems.get(n)
            if not s:
                return
            for d in s.deps:
                visit(d)
            order.append(n)

        for n in self.systems:
            visit(n)
        # composite / subtitle 强制排最后
        for tail in ("composite", "subtitle"):
            if tail in order:
                order.remove(tail)
                order.append(tail)
        self._order = order
        return order

    def report(self) -> str:
        lines = []
        tot = 0.0
        for n in self.order:
            s = self.systems[n]
            state = "启用" if s.enabled else "休眠"
            if s.enabled and s.calls:
                per = s.time_ms / s.calls
                tot += s.time_ms
                lines.append(f"  {n:<12}{state:<6}{s.calls:>5}次 "
                             f"{s.time_ms:>8.2f}ms  {per:>6.3f}ms/次")
            else:
                lines.append(f"  {n:<12}{state:<6}{'-':>5} "
                             f"{'-':>8}  {'-':>6}")
        lines.append(f"  {'合计':<12}{'':<6}{'':>5}{tot:>8.2f}ms")
        return "\n".join(lines)

    def reset_stats(self):
        for s_ in self.systems.values():
            s_._init_ctx = None
        for s in self.systems.values():
            s.calls = 0
            s.time_ms = 0.0

# --------------------------------------------------------------- 自检
# 铁律26：无自检 = 不通过。契约见 contracts/loop_engine.md
def self_check():
    """只读自检 + 最小调度冒烟，不渲染。返回 (ok, 项数)"""
    ok = True
    n = 0

    class _Ctx:
        pass

    def _mk():
        """搭一个最小引擎：skeleton <- physics <- composite/subtitle 常驻"""
        eng = LoopEngine()
        log = []

        def ini(ctx, tag):
            def f(c):
                log.append("init:" + tag)
                c.inited = getattr(c, "inited", []) + [tag]
            return f

        def upd(ctx_tag):
            def f(c, i, t):
                log.append("upd:" + ctx_tag)
            return f

        eng.register("skeleton", ini(None, "skeleton"), upd("skeleton"))
        eng.register("physics", ini(None, "physics"), upd("physics"),
                     deps=["skeleton"])
        eng.register("composite", ini(None, "composite"), upd("composite"))
        eng.register("subtitle", ini(None, "subtitle"), upd("subtitle"))
        eng.bind_tag("has_wind", ["physics"])
        eng.set_always(["composite", "subtitle"])
        return eng, log

    # 1) 依赖闭包递归展开
    n += 1
    eng, log = _mk()
    want = eng.resolve({"has_wind": True})
    if "skeleton" in want and "physics" in want:
        print("PASS 依赖闭包（physics 自动拉起 skeleton）")
    else:
        print("FAIL 依赖闭包漏了: %s" % sorted(want))
        ok = False

    # 2) 拓扑序：composite/subtitle 最后
    n += 1
    o = eng.order
    if o[-2:] == ["composite", "subtitle"]:
        print("PASS 拓扑序（composite/subtitle 排最后）")
    else:
        print("FAIL 拓扑序错误: %s" % o)
        ok = False

    # 3) 换 ctx 必须重新 init
    n += 1
    eng2, log2 = _mk()
    eng2.configure({"has_wind": True})
    c1, c2 = _Ctx(), _Ctx()
    eng2.run(2, c1)
    eng2.run(2, c2)
    if getattr(c1, "inited", None) and getattr(c2, "inited", None):
        print("PASS 换 ctx 重新 init（c1=%s c2=%s）"
              % (len(c1.inited), len(c2.inited)))
    else:
        print("FAIL 第二个 ctx 未 init -> 后续镜头会变空镜")
        ok = False

    # 4) 禁用系统零调用（按需真的省了）
    n += 1
    eng3, _ = _mk()
    eng3.configure({"has_wind": False})      # 无风
    c = _Ctx()
    eng3.run(3, c)
    if eng3.systems["physics"].calls == 0:
        print("PASS 无风时 physics 零调用（按需生效）")
    else:
        print("FAIL 无风仍调用 physics %d 次" % eng3.systems["physics"].calls)
        ok = False

    # 5) 铁律28：fps 取 framerate.FPS，不写死
    n += 1
    try:
        import framerate as fr
        if fr.FPS == 60 and abs(1.0 / fr.FPS - 1 / 60) < 1e-12:
            print("PASS fps 单一数据源（framerate.FPS=%d）" % fr.FPS)
        else:
            print("FAIL fps 源异常")
            ok = False
    except Exception as e:
        print("FAIL 无法 import framerate: %s" % e)
        ok = False

    # 6) register 后 order 缓存必须失效
    n += 1
    eng4, _ = _mk()
    _ = eng4.order                      # 先触发缓存
    eng4.register("movables", None, lambda c, i, t: None)
    if "movables" in eng4.order:
        print("PASS order 缓存在 register 后失效（新系统进入执行序列）")
    else:
        print("FAIL 新注册系统未进 order -> 永不执行")
        ok = False

    print("\n%d 项检查 -> %s" % (n, "PASS" if ok else "FAIL"))
    return ok, n


if __name__ == "__main__":
    import sys
    _ok, _ = self_check()
    sys.exit(0 if _ok else 1)
