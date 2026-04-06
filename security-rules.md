# SoundVerse 防火墙和安全组配置指南

本文档提供 SoundVerse 2.0 DEMO 版本在阿里云环境中的防火墙和安全组配置指南。

## 概述

SoundVerse 2.0 DEMO 版本采用微服务架构，需要配置适当的网络访问控制以确保系统安全。安全组配置遵循最小权限原则，只开放必要的端口。

## 1. 必要端口开放

### 1.1 对外访问端口（公网可访问）

| 端口 | 协议 | 服务 | 访问控制 | 说明 |
|------|------|------|----------|------|
| 22 | TCP | SSH | 仅管理员IP | 服务器管理访问 |
| 80 | TCP | HTTP | 0.0.0.0/0 | 前端HTTP访问（SLB监听端口） |
| 443 | TCP | HTTPS | 0.0.0.0/0 | 前端HTTPS访问（可选） |
| 8000 | TCP | HTTP | 0.0.0.0/0 | 后端API服务（SLB监听端口） |

### 1.2 内部服务端口（仅内网访问）

| 端口 | 协议 | 服务 | 访问控制 | 说明 |
|------|------|------|----------|------|
| 3306 | TCP | MySQL | 10.0.0.0/8 | 数据库服务（仅内网） |
| 6379 | TCP | Redis | 10.0.0.0/8 | 缓存服务（仅内网） |
| 5173 | TCP | HTTP | 10.0.0.0/8 | 前端容器内部端口 |
| 8000 | TCP | HTTP | 10.0.0.0/8 | API容器内部端口 |
| 9090 | TCP | HTTP | 10.0.0.0/8 | Prometheus监控（可选） |
| 9092 | TCP | HTTP | 10.0.0.0/8 | Prometheus外部访问（可选） |

## 2. 阿里云安全组配置

### 2.1 创建安全组

1. 登录阿里云控制台
2. 进入 **云服务器 ECS** → **网络与安全** → **安全组**
3. 点击 **创建安全组**
4. 输入安全组名称：`soundverse-sg`
5. 网络类型：**专有网络**
6. 选择对应的VPC

### 2.2 入方向规则配置

| 授权策略 | 协议类型 | 端口范围 | 授权对象 | 优先级 | 描述 |
|----------|----------|----------|----------|--------|------|
| 允许 | TCP | 22/22 | 管理员IP段 | 1 | SSH管理访问 |
| 允许 | TCP | 80/80 | 0.0.0.0/0 | 1 | HTTP前端访问 |
| 允许 | TCP | 443/443 | 0.0.0.0/0 | 1 | HTTPS前端访问 |
| 允许 | TCP | 8000/8000 | 0.0.0.0/0 | 1 | API服务访问 |
| 允许 | TCP | 3306/3306 | 10.0.0.0/8 | 2 | MySQL内网访问 |
| 允许 | TCP | 6379/6379 | 10.0.0.0/8 | 2 | Redis内网访问 |
| 允许 | TCP | 5173/5173 | 10.0.0.0/8 | 2 | 前端容器内网 |
| 允许 | TCP | 8000/8000 | 10.0.0.0/8 | 2 | API容器内网 |
| 允许 | TCP | 9090/9090 | 10.0.0.0/8 | 2 | Prometheus内网 |
| 允许 | TCP | 9092/9092 | 10.0.0.0/8 | 2 | Prometheus外部 |

### 2.3 出方向规则配置（默认）

| 授权策略 | 协议类型 | 端口范围 | 授权对象 | 优先级 | 描述 |
|----------|----------|----------|----------|--------|------|
| 允许 | 全部 | -1/-1 | 0.0.0.0/0 | 1 | 全部出站流量 |

**注意**：生产环境可根据需要限制出站流量。

## 3. 防火墙配置（ECS实例）

### 3.1 Ubuntu/Debian系统 (ufw)

```bash
# 安装ufw
sudo apt update
sudo apt install ufw -y

# 设置默认策略
sudo ufw default deny incoming
sudo ufw default allow outgoing

# 开放必要端口
sudo ufw allow 22/tcp comment 'SSH管理'
sudo ufw allow 80/tcp comment 'HTTP前端'
sudo ufw allow 443/tcp comment 'HTTPS前端'
sudo ufw allow 8000/tcp comment 'API服务'

# 允许内网端口（如果运行在相同服务器）
sudo ufw allow from 10.0.0.0/8 to any port 3306 comment 'MySQL内网'
sudo ufw allow from 10.0.0.0/8 to any port 6379 comment 'Redis内网'
sudo ufw allow from 10.0.0.0/8 to any port 5173 comment '前端容器内网'
sudo ufw allow from 10.0.0.0/8 to any port 8000 comment 'API容器内网'

# 启用防火墙
sudo ufw enable
sudo ufw status verbose
```

### 3.2 CentOS/RHEL系统 (firewalld)

```bash
# 安装firewalld
sudo yum install firewalld -y
sudo systemctl start firewalld
sudo systemctl enable firewalld

# 开放端口
sudo firewall-cmd --permanent --add-port=22/tcp --zone=public
sudo firewall-cmd --permanent --add-port=80/tcp --zone=public
sudo firewall-cmd --permanent --add-port=443/tcp --zone=public
sudo firewall-cmd --permanent --add-port=8000/tcp --zone=public

# 添加内网区域
sudo firewall-cmd --permanent --new-zone=internal
sudo firewall-cmd --permanent --zone=internal --add-source=10.0.0.0/8
sudo firewall-cmd --permanent --zone=internal --add-port=3306/tcp
sudo firewall-cmd --permanent --zone=internal --add-port=6379/tcp
sudo firewall-cmd --permanent --zone=internal --add-port=5173/tcp
sudo firewall-cmd --permanent --zone=internal --add-port=8000/tcp

# 重载配置
sudo firewall-cmd --reload
sudo firewall-cmd --list-all
```

## 4. Docker网络配置

### 4.1 Docker网络隔离

SoundVerse使用自定义Docker网络 `SoundVerse-network`，提供容器间隔离通信：

```bash
# 查看网络配置
docker network ls
docker network inspect SoundVerse-network

# 容器内部使用服务名通信
# 例如：API容器通过 "mysql" 主机名访问MySQL服务
```

### 4.2 端口映射规则

在 `docker-compose.yml` 中配置的端口映射：

```yaml
services:
  mysql:
    ports:
      - "3306:3306"  # 主机3306 -> 容器3306
  
  redis:
    ports:
      - "63792:6379"  # 主机63792 -> 容器6379
  
  api:
    ports:
      - "8000:8000"  # 主机8000 -> 容器8000
  
  frontend-demo:
    ports:
      - "5173:5173"  # 主机5173 -> 容器5173
```

## 5. SLB与安全组协同配置

### 5.1 SLB监听端口与后端端口

| SLB监听端口 | 后端ECS端口 | 协议 | 健康检查 |
|-------------|------------|------|----------|
| 80 | 5173 | HTTP | `/` |
| 443 | 5173 | HTTPS | `/` (可选) |
| 8000 | 8000 | HTTP | `/api/health` |

### 5.2 安全组与SLB联动

1. **SLB安全组**：为SLB实例配置安全组，允许80、443、8000端口入站
2. **ECS安全组**：为后端ECS配置安全组，允许SLB安全组访问5173和8000端口
3. **内网通信**：ECS安全组允许内网IP段访问3306、6379等内部服务端口

## 6. 安全最佳实践

### 6.1 最小权限原则

1. **仅开放必要端口**：关闭所有非必要端口
2. **IP白名单**：管理端口（SSH）仅对管理员IP开放
3. **内网隔离**：数据库、缓存等服务仅内网可访问
4. **定期审计**：定期检查端口开放情况和访问日志

### 6.2 网络分段

1. **VPC划分**：将不同环境（生产、测试、开发）部署在不同VPC
2. **子网隔离**：在VPC内划分子网，将Web层、应用层、数据层分离
3. **安全组分层**：为不同层的ECS配置不同的安全组策略

### 6.3 监控与告警

1. **异常连接监控**：监控非正常时间或来源的连接尝试
2. **端口扫描检测**：检测端口扫描行为
3. **流量异常告警**：设置流量突增或突降的告警

## 7. 故障排查

### 7.1 常见问题

1. **无法访问服务**
   - 检查安全组规则是否正确
   - 检查防火墙是否开放相应端口
   - 检查SLB健康检查是否通过

2. **内网服务无法通信**
   - 检查内网安全组规则
   - 检查Docker网络配置
   - 检查容器间DNS解析

3. **端口冲突**
   - 检查端口是否被其他进程占用
   - 修改docker-compose.yml中的端口映射

### 7.2 诊断命令

```bash
# 检查端口监听
netstat -tlnp
ss -tlnp

# 检查防火墙规则
sudo ufw status  # Ubuntu
sudo firewall-cmd --list-all  # CentOS

# 检查Docker容器状态
docker ps
docker logs <container_name>

# 测试端口连通性
telnet <ip> <port>
nc -zv <ip> <port>
```

## 8. 附录

### 8.1 默认端口参考

- **SSH**: 22
- **HTTP**: 80
- **HTTPS**: 443
- **MySQL**: 3306
- **Redis**: 6379
- **Prometheus**: 9090
- **前端服务**: 5173
- **API服务**: 8000

### 8.2 相关文档

- [SLB配置指南](SLB-CONFIGURATION.md) - 阿里云SLB详细配置
- [部署脚本](deploy.sh) - 自动化部署脚本
- [Docker Compose配置](docker-compose.yml) - 服务容器配置

---

**更新日志**  
- 2026-04-06: 初始版本创建，包含阿里云安全组和防火墙配置