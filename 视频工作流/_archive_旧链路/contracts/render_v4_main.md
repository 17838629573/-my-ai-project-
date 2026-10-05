[TOP] render_v4_main @SHOT/_top  d6  in=1  gen:contract_gen
does: render_v4 自检与出片主流程（原 182 行上帝函数抽出）。
api: self_check, main
impl: 入口 main
up: actors,character_sheet,film_assemble,framerate,photo_rules,physics,render_v4,systems
down: render_v4
edit: actors,character_sheet,film_assemble,framerate,photo_rules,physics,render_v4,systems   # 改render_v4_main须同步核对这些文件
rule: T19
why : IMPROVE_render_v4_main.md
