FROM python:3.11-slim

WORKDIR /app

# 安装依赖(国内镜像源由行云预处理器自动注入, 此处不手动配置)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件(taxonomy.json随代码进镜像; records.db运行时生成, 已在.dockerignore排除)
COPY . .

# 创建数据目录(SQLite运行时写入)
RUN mkdir -p /app/data

# HF Spaces要求容器监听7860端口(可通过README frontmatter app_port调整)
EXPOSE 7860

# 端口通过环境变量控制, 默认7860(HF Spaces), 行云设PORT=8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]