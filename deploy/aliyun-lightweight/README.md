# 阿里云轻量应用服务器部署指南

## 方案概述

将 `特殊教育康复决策智能体` 部署到阿里云轻量应用服务器，使用 SQLite 本地数据库持久化存储。

## 前提条件

1. 阿里云账号
2. 已购买轻量应用服务器（推荐配置：2核2G，Ubuntu 22.04）
3. 本地代码已准备好

## 部署步骤

### 第1步：购买并配置服务器

1. 登录阿里云控制台 → 轻量应用服务器
2. 创建实例：
   - 地域：选择离你最近的
   - 镜像：Ubuntu 22.04 LTS
   - 套餐：2核2G（约60元/月，新用户有优惠）
3. 设置 root 密码
4. **配置防火墙**：
   - 进入实例详情 → 防火墙 → 添加规则
   - 协议：TCP，端口：8080，来源：0.0.0.0/0

### 第2步：上传代码到服务器

**方式A：使用 git（推荐）**

```bash
# 在服务器上执行
git clone <你的GitHub仓库地址> /opt/special-edu-agent
```

**方式B：使用 WinSCP / FileZilla**

1. 下载 WinSCP（Windows）或 FileZilla
2. 连接服务器：IP地址 + root + 密码
3. 将本地代码上传到 `/opt/special-edu-agent`

### 第3步：运行部署脚本

```bash
# SSH连接到服务器
ssh root@<你的服务器IP>

# 进入代码目录
cd /opt/special-edu-agent

# 给脚本执行权限并运行
chmod +x deploy/aliyun-lightweight/deploy.sh
bash deploy/aliyun-lightweight/deploy.sh
```

### 第4步：验证部署

```bash
# 查看服务状态
systemctl status special-edu-agent

# 查看日志
journalctl -u special-edu-agent -f

# 测试API
curl http://<你的服务器IP>:8080/api/health
```

### 第5步：灌入演示数据（可选）

```bash
curl -X POST http://<你的服务器IP>:8080/api/seed
```

### 第6步：Coze接入

在 Coze 中创建插件时，填入你的服务器地址：

```
Base URL: http://<你的服务器IP>:8080
```

> 注意：生产环境建议配置 HTTPS（使用阿里云SSL证书或Nginx反向代理）

## 常用运维命令

```bash
# 查看服务状态
systemctl status special-edu-agent

# 查看实时日志
journalctl -u special-edu-agent -f

# 重启服务
systemctl restart special-edu-agent

# 停止服务
systemctl stop special-edu-agent

# 查看数据库
sqlite3 /opt/special-edu-agent/data/records.db "SELECT * FROM records LIMIT 5;"
```

## 数据备份

SQLite 数据库文件位于 `/opt/special-edu-agent/data/records.db`，建议定期备份：

```bash
# 手动备份
cp /opt/special-edu-agent/data/records.db /backup/records_$(date +%Y%m%d).db

# 或者设置定时任务
crontab -e
# 添加：每天凌晨3点备份
0 3 * * * cp /opt/special-edu-agent/data/records.db /backup/records_$(date +\%Y\%m\%d).db
```

## 升级部署

更新代码后重新部署：

```bash
cd /opt/special-edu-agent
git pull  # 或重新上传代码
source venv/bin/activate
pip install -r requirements.txt
systemctl restart special-edu-agent
```