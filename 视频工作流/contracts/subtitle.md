# subtitle ·绿 字幕  史:notes/subtitle.md

接口: draw_subtitle(bgr,text,alpha,margin_bottom=0.25,max_chars=14,stroke=4),
      subtitle_alpha(i,n,fade_frames=6), check_timing(seconds,chars), get_font
规范: 字号=画面高5%±1%(GY/T357-2021)｜白字+黑边宽4不透明｜底距0.25
     每行≤14字｜CPS17-20
避头尾: 行首禁=。，！？、；：）」』】》….,!?;:)]}｜行尾禁=（「『【《([{

**self_check()（铁律26）**
`python3 subtitle.py` 默认自检，不渲染。检查项：
  1. 字号 = 画面高 5% ±1%（GY/T357-2021）
  2. 避头尾规则生效（行首禁 。，！？ 等）
  3. check_timing CPS 落在 17-20
  4. 【铁律28】check_timing(fps) 默认取 framerate.FPS，不得写死 24
  5. subtitle_alpha 淡入淡出：起止为 0、中段为 1、单调
