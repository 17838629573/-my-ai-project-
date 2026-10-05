#!/usr/bin/env python3
"""Stage 3.5：驱动生图队列，打印代码下发的参数与提示词。
依赖: build_phase_gen scene_spec
被依赖: 无（人工执行，供 AI 按批生图）
铁律: T81 一次只生成一种物体的一类图 / T97 结构性量由代码下发
"""
import json
import sys
import build_phase_gen as G

spec = json.load(open("scene_spec.json", encoding="utf-8"))
U = float(spec["wind"]["U"])
print(f"=== 场景 {spec['名称']} | 风 {spec['wind']['level']}级 U={U} m/s ===")
print(f"风格: {spec.get('style')}")
q = G.emit_gen_queue(spec, U)
print(f"批次总数: {q['n']}")
