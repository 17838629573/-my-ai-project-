[S] film_assemble_render @SHOT/assemble  d4  in=1  gen:contract_gen
does: film_assemble 分镜渲染与自检（原 165 行抽出）。
api: self_check, render_one
impl: 入口 self_check
up: character_sheet,chroma,film_assemble,framerate,photo_rules,subtitle
down: film_assemble
edit: character_sheet,chroma,film_assemble,framerate,photo_rules,subtitle   # 改film_assemble_render须同步核对这些文件
rule: T13 T28
why : IMPROVE_film_assemble_render.md
