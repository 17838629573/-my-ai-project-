[FACT] _migrate_common   86行   机器生成，勿手改
doc: 迁移脚手架：把业务模块的内联实现改为调用 _common。
api:
  L20 active(path)
  L46 main()
calls_in: main→active
calls_out: MECH,NEED_HUMAN,files,hits_h,hits_m,os,re,rel
guard: return@L22
const: ROOT, ACTIVE[0], MECH[4], NEED_HUMAN[4]
main: __main__@L85
up: -
down: -
