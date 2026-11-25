# NLP 风险识别微服务镜像（项目 15）
# 基础镜像用华为云同步的 docker.io 镜像，避免 Docker Hub 拉取超时（表 15-9 第 1 条）
FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/library/python:3.10-slim

WORKDIR /app

# 先复制依赖清单，利用镜像层缓存：改代码时不用重装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY app.py .

EXPOSE 5000

# 健康检查：容器自身每 30 秒探一次 /health，状态转 unhealthy 时便于排查
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=2).status == 200 else 1)"

CMD ["python", "app.py"]