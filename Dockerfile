FROM python:3.11-slim

WORKDIR /app

# 安装依赖(国内镜像源由行云预处理器自动注入, 此处不手动配置)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件(taxonomy.json随代码进镜像; records.db运行时生成, 已在.dockerignore排除)
COPY . .

# 创建数据目录(SQLite运行时写入)
RUN mkdir -p /app/data

# 行云K8s ingress仅路由容器8080端口
EXPOSE 8080

# 绑定0.0.0.0:8080(行云硬性要求, 不能用localhost/127.0.0.1)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]