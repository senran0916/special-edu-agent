# 阿里云ECS免费试用部署指南

## 适用场景

- 阿里云新用户免费领取ECS服务器（1核2G，3个月免费）
- 需要持久化SQLite数据库
- 希望一键部署，自动管理服务

---

## 你需要做的（按顺序）

### 第1步：领取阿里云ECS免费试用

1. 打开 [阿里云免费试用页面](https://free.aliyun.com/)
2. 找到 **"云服务器ECS"** 免费试用（新用户可领）
3. 点击 **"立即试用"**
4. 配置选择：
   - **地域**：选择离你最近的（如华东1杭州）
   - **实例规格**：1核2G（免费试用的规格）
   - **镜像**：Ubuntu 22.04 64位
   - **系统盘**：40GB（默认）
   - **带宽**：按流量计费 1Mbps（默认）
5. 勾选协议，点击 **"立即试用"**
6. 等待实例创建完成（约1-2分钟）

### 第2步：配置安全组（开放端口）

这是**最关键的一步**，否则外网无法访问你的服务。

1. 进入ECS控制台 → 找到你的实例 → 点击 **"安全组"**
2. 点击安全组ID进入详情
3. 点击 **"手动添加"** 规则：
   - 授权策略：允许
   - 优先级：1
   - 协议类型：自定义TCP
   - 端口范围：**8080/8080**
   - 授权对象：**0.0.0.0/0**
   - 描述：API服务端口
4. 点击 **"保存"**

> 如果你还想用SSH连接，确保22端口也是开放的（默认应该已开放）

### 第3步：获取服务器连接信息

1. 在ECS实例列表中，找到你的实例
2. 记录以下信息：
   - **公网IP**（如 47.100.xxx.xxx）
   - **实例ID**
3. 重置密码（如果还没设置）：
   - 实例详情 → 更多 → 密码/密钥 → 重置实例密码
   - 设置root密码并记住

### 第4步：上传代码到服务器

**方式A：使用 Git（推荐，如果你代码在GitHub）**

```bash
# 1. 先把本地代码推送到GitHub（如果还没推）
# 在本地项目目录执行：
git init
git add .
git commit -m "initial commit"
git branch -M main
git remote add origin https://github.com/你的用户名/你的仓库名.git
git push -u origin main

# 2. SSH连接到ECS服务器
ssh root@<你的ECS公网IP>
# 输入密码

# 3. 在服务器上克隆代码
git clone https://github.com/你的用户名/你的仓库名.git /opt/special-edu-agent
```

**方式B：使用 WinSCP（Windows用户）**

1. 下载 [WinSCP](https://winscp.net/)
2. 打开WinSCP，配置连接：
   - 文件协议：SFTP
   - 主机名：你的ECS公网IP
   - 用户名：root
   - 密码：你设置的root密码
3. 连接后，把本地项目文件夹拖到服务器的 `/opt/` 目录下
4. 重命名为 `special-edu-agent`

### 第5步：运行部署脚本

```bash
# SSH连接到服务器
ssh root@<你的ECS公网IP>

# 进入代码目录
cd /opt/special-edu-agent

# 给脚本执行权限
chmod +x deploy/aliyun-ecs/deploy.sh

# 运行部署脚本
bash deploy/aliyun-ecs/deploy.sh
```

脚本会自动完成：
- 更新系统
- 安装Python3、pip、git、sqlite3
- 创建Python虚拟环境
- 安装项目依赖
- 初始化SQLite数据库
- 创建systemd服务并启动

### 第6步：验证部署

```bash
# 查看服务是否运行
systemctl status special-edu-agent

# 查看日志
journalctl -u special-edu-agent -f
```

在浏览器或Postman中访问：

```
http://<你的ECS公网IP>:8080/api/health
```

如果返回 `{"status":"ok"...}`，说明部署成功！

### 第7步：灌入演示数据（可选）

```bash
curl -X POST http://<你的ECS公网IP>:8080/api/seed
```

### 第8步：Coze接入

在Coze中创建插件时：

- **Base URL**：`http://<你的ECS公网IP>:8080`
- 导入以下接口：
  - `POST /api/records` — 提交康复记录
  - `GET /api/report` — 获取完整报告
  - `POST /api/analyze` — 触发分析

---

## 常用运维命令

```bash
# 查看服务状态
systemctl status special-edu-agent

# 查看实时日志（按Ctrl+C退出）
journalctl -u special-edu-agent -f

# 重启服务
systemctl restart special-edu-agent

# 停止服务
systemctl stop special-edu-agent

# 查看数据库内容
sqlite3 /opt/special-edu-agent/data/records.db "SELECT COUNT(*) FROM records;"
```

---

## 数据备份

```bash
# 手动备份数据库
cp /opt/special-edu-agent/data/records.db /backup/records_$(date +%Y%m%d).db

# 设置定时自动备份（每天凌晨3点）
crontab -e
# 添加下面这行：
0 3 * * * cp /opt/special-edu-agent/data/records.db /backup/records_$(date +\%Y\%m\%d).db
```

---

## 升级部署

更新代码后：

```bash
cd /opt/special-edu-agent
git pull  # 或重新上传代码
source venv/bin/activate
pip install -r requirements.txt
systemctl restart special-edu-agent
```

---

## 常见问题

### Q1: 访问 `http://IP:8080` 没反应？
- 检查安全组是否开放了8080端口
- 检查服务是否运行：`systemctl status special-edu-agent`
- 检查防火墙：`ufw status`，如果开启了就放行8080：`ufw allow 8080`

### Q2: 免费试用到期后怎么办？
- 续费ECS（约99元/年，学生更便宜）
- 或迁移到付费版/其他平台

### Q3: 想用HTTPS？
- 购买域名并备案（国内服务器需要备案）
- 申请阿里云免费SSL证书
- 配置Nginx反向代理（需要额外配置）