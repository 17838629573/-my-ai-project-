[FACT] build_phase_setup   86行   机器生成，勿手改
doc: 出片前置：基线探测 + 比例尺 + 路径校验。
api:
  L23 setup_baseline(bg,spec,W)  # 基线：探测后必须校验落在可行走面上（铁律98）。
  L45 setup_scale(spec,baseline_y,wind_dir)  # 比例尺 + 风响应。px_per_m 由 scale_map 唯一给出（铁律86），此处禁重算。
  L72 setup_path(spec,bg,W,H,px_per_m)  # 路径：AI 声明控制点，代码不猜。越界报错（铁律96），
calls_out: CW,GL,PA,PAL,SM,_ref,smap,spec
guard: return@L29, raise@L35, raise@L79
const: W_DIR_DEFAULT=1.0
up: _px,build_util,cloth_wire,groundline,path,path_align,scale_map,wind_response
down: build_video
