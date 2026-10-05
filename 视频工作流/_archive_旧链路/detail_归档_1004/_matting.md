[FACT] _matting   156行   机器生成，勿手改
doc: 抠图/matting：从 sprite 单格提取软 alpha 前景。
api:
  L40 auto_trimap(bgr,border_ratio,fg_ratio,unknown_band)  # 自动 trimap：边缘环=确定背景，中心矩形=确定前景，中间=未知。
  L83 grabcut_alpha(bgr,trimap,iters)  # GrabCut：以 trimap 初始化，返回软 alpha（0-255 uint8）。
  L99 keep_center_component(alpha)  # 只保留包含图像中心的连通域（铁律112：禁保留整格四方形）。
  L121 feather_alpha(alpha,radius)  # 硬 alpha → 软 alpha：边缘羽化 radius 像素。
  L137 matte_cell(bgr,border_ratio,feather,iters)  # 单格完整抠图：trimap → GrabCut → 中心连通域 → 羽化。
  L146 split_sheet(sheet,cols,rows)  # 按网格切分图集，返回 list[ndarray]，行优先。
internal:
  L29 _border_ring(h,w,ratio)
calls_in: auto_trimap→_border_ring, matte_cell→auto_trimap, matte_cell→feather_alpha, matte_cell→grabcut_alpha, matte_cell→keep_center_component
calls_out: alpha,bgr,cells,cv2,fg,np,ring_px
guard: raise@L45, raise@L52, raise@L86, return@L103, return@L112, return@L123, raise@L148
up: -
down: -
