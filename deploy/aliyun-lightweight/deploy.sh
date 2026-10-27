#!/bin/bash
# =============================================================================
# 阿里云轻量应用服务器部署脚本
# 特殊教育康复决策智能体 - 一键部署
# =============================================================================

set -e

APP_DIR="/opt/special-edu-agent"
APP_PORT=${APP_PORT:-8080}
PYTHON_VERSION="3.11"

echo "========================================"
echo "  特殊教育康复决策智能体 - 部署脚本"
echo "========================================"

# ---- 1. 安装依赖 ----
echo "[1/6] 安装系统依赖..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv git curl

# ---- 2. 创建应用目录 ----
echo "[2/6] 创建应用目录..."
mkdir -p "$APP_DIR"
cd "$APP_DIR"

# ---- 3. 复制代码（假设代码已通过git clone或scp上传）----
echo "[3/6] 检查代码..."
if [ ! -f "$APP_DIR/app/main.py" ]; then
    echo "错误: 未找到应用代码。请先上传代码到 $APP_DIR"
    echo "方式1: git clone <你的仓库地址> $APP_DIR"
    echo "方式2: 用 WinSCP/FileZilla 上传代码"
    exit 1
fi

# ---- 4. 创建虚拟环境并安装依赖 ----
echo "[4/6] 安装Python依赖..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

# ---- 5. 初始化数据库 ----
echo "[5/6] 初始化数据库..."
python3 -c "from app import database as db; db.init_db(); print('数据库初始化完成')"

# ---- 6. 创建systemd服务 ----
echo "[6/6] 创建系统服务..."
cat > /etc/systemd/system/special-edu-agent.service << EOF
[Unit]
Description=特殊教育康复决策智能体 API
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
Environment="PORT=$APP_PORT"
Environment="DB_PATH=$APP_DIR/data/records.db"
ExecStart=$APP_DIR/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port $APP_PORT
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 重载systemd并启动
systemctl daemon-reload
systemctl enable special-edu-agent
systemctl start special-edu-agent

echo ""
echo "========================================"
echo "  部署完成!"
echo "========================================"
echo ""
echo "服务状态:"
systemctl status special-edu-agent --no-pager
echo ""
echo "访问地址:"
echo "  健康检查: http://<你的服务器IP>:$APP_PORT/api/health"
echo "  API文档:  http://<你的服务器IP>:$APP_PORT/docs"
echo ""
echo "常用命令:"
echo "  查看日志: journalctl -u special-edu-agent -f"
echo "  重启服务: systemctl restart special-edu-agent"
echo "  停止服务: systemctl stop special-edu-agent"
echo ""