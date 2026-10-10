# 契约: 根目录/Makefile
#   一句话: 把所有常用命令收敛成 make <目标>，避免用户记 _proc 下的长路径
#   依据: 第三方评估"使用门槛不低、需先跑 gen_index 再跑测试"，此处固化顺序

PY ?= python3
PROC := _proc

.PHONY: help install demo cafe test check gate index api docker clean

help:                       ## 列出所有可用目标
	@grep -E '^[a-z-]+:.*?## ' Makefile | awk -F':.*?## ' '{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install:                    ## 装运行+门禁依赖（首次必做）
	$(PY) -m pip install -r requirements.txt

demo:                       ## 走 beat 时间线出演示片
	$(PY) $(PROC)/beat_demo.py

cafe:                       ## 咖啡馆 12 秒四段动作
	$(PY) $(PROC)/showreel/cafe.py

test:                       ## 跑门检（45 项）
	$(PY) $(PROC)/tests/run_all.py

check:                      ## 架构契约扫描
	$(PY) $(PROC)/check.py

gate:                       ## 统一门禁入口（--json 可机读）
	$(PY) $(PROC)/tools/gate.py

index:                      ## 从契约块重生成 INDEX.md（改代码后必跑）
	$(PY) $(PROC)/gen_index.py

api:                        ## 从契约块重生成 API.md（能力接口文档）
	$(PY) $(PROC)/gen_api.py

docker:                     ## 构建镜像并跑一遍门检验环境
	docker build -t proc-anim . && docker run --rm proc-anim

clean:                      ## 清产物（mp4/索引图），不动代码
	rm -f $(PROC)/*.mp4 $(PROC)/*.png $(PROC)/__pycache__ -r
