# 用官方 Python 镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app


# 安装 vim 及基础工具
RUN apt-get update && apt-get install -y --no-install-recommends vim \
    && rm -rf /var/lib/apt/lists/

# 复制 requirements.txt
COPY requirements.txt .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 把代码复制进去（如果有）
COPY . .

# 默认启动 bash（你也可以改成 python app.py）
CMD ["/bin/bash"]

