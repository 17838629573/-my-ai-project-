# 契约: 根目录/Dockerfile
#   一句话: 一次性搭好可运行环境，使"克隆即可跑"，不依赖本地 Python 版本
#   依据: 第三方独立评估指出开箱即用仅 5.5/10（无 Dockerfile/无一键脚本）
FROM python:3.10-slim

LABEL org.opencontainers.image.title="程序化动画引擎（视频工作流）"
LABEL org.opencontainers.image.description="骨架->胶囊->SDF->光栅化->mp4，不调用任何生图模型"

WORKDIR /app

# 只装运行与门禁依赖；headless 版 opencv 免 libGL 等系统库
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY _proc /app/_proc

# 产物目录：容器内跑出的 mp4 挂到这里，宿主可直接取
VOLUME ["/app/out"]
ENV PYTHONUNBUFFERED=1

# 默认跑门检，验环境是否健康；跑演示片换: docker run <img> demo
CMD ["python3", "_proc/tests/run_all.py"]
