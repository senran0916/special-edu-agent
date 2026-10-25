FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制项目文件
COPY . .

# 创建数据目录
RUN mkdir -p /app/data

# 暴露端口(Render通过PORT环境变量注入, 默认8000)
ENV PORT=8000
EXPOSE 8000

# 启动命令
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]