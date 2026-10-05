[S] foot_lock @SHOT/skel  d0  in=1  gen:contract_gen
does: 足锁：接触时锁定脚的世界坐标，切换用三次惯性化平滑。
api: cubic_inertialize, self_check
const: FOOT_LOCK_DIST, FOOT_UNLOCK_DIST, FOOT_INERT_TIME
impl: 入口 self_check
down: pose
edit: pose   # 改foot_lock须同步核对这些文件
why : IMPROVE_foot_lock.md
