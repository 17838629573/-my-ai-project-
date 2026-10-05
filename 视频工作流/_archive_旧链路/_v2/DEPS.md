# _v2 依赖图（机器生成）

约束：禁止环；下层禁止反向依赖上层。

## 模块
spec.py       158行  依赖: （无）
flowsplit.py  201行  依赖: （无）
interp.py     167行  依赖: flowsplit
keygen.py     153行  依赖: spec
chain.py      169行  依赖: flowsplit
build.py      277行  依赖: spec,keygen,flowsplit,interp,chain

## 边
spec -> keygen
flowsplit -> interp
flowsplit -> chain
spec -> build
keygen -> build
flowsplit -> build
interp -> build
chain -> build

节点6 边8 环: 无

S3 走图集：一次生图 → sheet_cut 切格 → N 张关键帧（漂移只发生 1 次）