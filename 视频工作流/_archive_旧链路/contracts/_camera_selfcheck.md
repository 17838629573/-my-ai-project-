[S] _camera_selfcheck @ATOM/cam  d2  in=0  gen:contract_gen
does: _camera 自检（独立模块，避免撑大核心文件）
api: ck, main
const: FAILS
impl: main → ck
up: _camera
edit: _camera   # 改_camera_selfcheck须同步核对这些文件
why : IMPROVE__camera_selfcheck.md
