# SoundVerse 部署与维护指南

本文档提供 SoundVerse 2.0 DEMO 版本的部署、更新、监控和维护说明。

## 环境要求

### 服务器规格
- **操作系统**: Ubuntu 20.04 LTS 或更高版本 (推荐 Ubuntu 22.04 LTS)
- **CPU**: 2 核或以上 (推荐 4 核)
- **内存**: 4GB 或以上 (推荐 8GB)
- **磁盘**: 50GB 或以上可用空间
- **网络**: 公网 IP，开放端口 (见下文)

### 软件依赖
必须在服务器上预安装以下软件：

| 软件 | 版本要求 | 安装命令 (Ubuntu) |
|------|----------|-------------------|
| Docker | 24.0+ | `curl -fsSL https://get.docker.com | sh` |
| Docker Compose | 2.20+ | `apt install docker-compose-plugin` |
| SSH Server | 已安装并运行 | `apt install openssh-server` |
| jq (可选) | 最新版 | `apt install jq` |

### 网络端口配置
部署前请确保以下端口在防火墙中开放：

| 端口 | 服务 | 访问方式 | 说明 |
|------|------|----------|------|
| 22 | SSH | TCP | 远程连接和文件传输 |
| 80 | HTTP | TCP | 前端访问 (SLB转发) |
| 8000 | FastAPI | TCP | 后端 API 服务 |
| 5173 | 前端开发 | TCP | 前端 DEMO 服务 (开发环境) |
| 3306 | MySQL | TCP | 数据库服务 (可选) |
| 6379 | Redis | TCP | 缓存服务 (可选) |
| 9092 | Prometheus | TCP | 监控服务 (可选) |

### 阿里云资源准备
- **阿里云账号**: 已注册并实名认证
- **VPC网络**: 创建专有网络和虚拟交换机
- **安全组**: 配置允许上述端口的入站规则
- **SLB实例**: 配置监听端口转发 (阶段4任务)
- **OSS存储**: 创建存储桶并获取访问密钥 (可选)

## 首次部署步骤

### 1. 本地环境准备
在部署前，请确保本地开发环境已准备好部署文件：

```bash
# 克隆项目
git clone https://github.com/your-username/SoundVerse.git
cd SoundVerse

# 检查部署文件是否存在
ls -la deploy.sh update.sh docker-compose.prod.yml deploy-config.example.json
# 应能看到以上文件

# 复制环境配置模板
cp .env.example .env
# 编辑 .env 文件，填入实际的阿里云API密钥等配置
```

### 2. 配置部署参数
创建部署配置文件 `deploy-config.json` (基于模板):

```bash
# 复制配置文件模板
cp deploy-config.example.json deploy-config.json

# 编辑配置文件
vim deploy-config.json
```

配置文件示例:
```json
{
  "server_ip": "your-server-ip",
  "app_name": "soundverse-demo",
  "backup_dir": "./backups",
  "ssh_user": "root",
  "ssh_port": 22,
  "api_port": 8000,
  "frontend_port": 5173
}
```

### 3. 配置SSH免密登录 (推荐)
为简化部署过程，建议配置SSH免密登录到目标服务器:

```bash
# 生成SSH密钥对 (如果尚未生成)
ssh-keygen -t rsa -b 4096

# 将公钥复制到服务器
ssh-copy-id -p 22 root@your-server-ip

# 测试连接
ssh root@your-server-ip "echo SSH连接成功"
```

### 4. 执行一键部署
运行主部署脚本:

```bash
# 赋予执行权限
chmod +x deploy.sh

# 执行部署 (生产环境)
./deploy.sh prod your-server-ip

# 或者使用配置文件 (推荐)
./deploy.sh prod
```

### 5. 部署过程详解
部署脚本将自动执行以下步骤:

1. **本地检查**: 验证必要文件和命令
2. **远程数据库备份**: 如果存在旧版本数据库，自动备份
3. **代码同步**: 使用rsync将代码传输到服务器 `/opt/soundverse-demo/`
4. **远程构建**: 在服务器上构建Docker镜像
5. **服务启动**: 启动所有容器服务
6. **数据库迁移**: 自动运行数据库初始化脚本
7. **向量索引初始化**: 初始化DashVector向量索引
8. **健康检查**: 验证前后端服务是否正常运行

### 6. 验证部署成功
部署完成后，验证服务可正常访问:

```bash
# 检查前端服务
curl -f http://your-server-ip:5173

# 检查后端健康状态
curl -f http://your-server-ip:8000/health

# 检查后端API文档
curl -f http://your-server-ip:8000/docs
```

预期响应:
- 前端: 返回HTML页面
- 健康检查: `{"status":"healthy","services":{...}}`
- API文档: Swagger UI界面

## 更新流程

### 快速更新 (仅代码变更)
当仅修改前端代码或不涉及数据库变更时，使用快速更新脚本:

```bash
# 快速更新前端代码
./update.sh your-server-ip

# 或使用配置文件
./update.sh
```

**更新流程**:
1. 同步代码文件到服务器 (排除node_modules等)
2. 重启前端容器 (热重载)
3. 保持其他服务运行

### 完整更新 (涉及数据库或后端变更)
当修改数据库模型、后端API或环境配置时，使用完整部署:

```bash
# 完整部署更新
./deploy.sh prod your-server-ip
```

**完整更新流程**:
1. 自动备份现有数据库
2. 同步所有代码文件
3. 重新构建Docker镜像
4. 重启所有服务
5. 运行数据库迁移 (如有)

### 更新最佳实践
1. **测试环境先行**: 先在测试服务器验证更新
2. **备份策略**: 重要更新前手动备份数据库
3. **分阶段更新**: 大规模更新分批次进行
4. **监控更新过程**: 实时观察日志和健康状态

## 监控维护

### 服务状态监控

#### 容器状态检查
```bash
# 查看所有容器状态
ssh root@your-server-ip "cd /opt/soundverse-demo && docker-compose ps"

# 查看容器日志
ssh root@your-server-ip "cd /opt/soundverse-demo && docker-compose logs -f"

# 查看特定服务日志
ssh root@your-server-ip "cd /opt/soundverse-demo && docker-compose logs -f api"
ssh root@your-server-ip "cd /opt/soundverse-demo && docker-compose logs -f frontend-demo"
```

#### 健康检查端点
系统提供多个健康检查端点:

| 端点 | 用途 | 预期响应 |
|------|------|----------|
| `http://your-server-ip:8000/health` | 综合健康状态 | `{"status":"healthy",...}` |
| `http://your-server-ip:8000/docs` | API文档 | Swagger UI |
| `http://your-server-ip:5173` | 前端服务 | 应用界面 |

#### 资源监控
```bash
# 查看服务器资源使用
ssh root@your-server-ip "top -n 1"

# 查看Docker资源使用
ssh root@your-server-ip "docker stats --no-stream"

# 查看磁盘空间
ssh root@your-server-ip "df -h"
```

### 日志管理
日志文件位于以下位置:

| 服务 | 日志位置 | 查看命令 |
|------|----------|----------|
| 后端API | `/opt/soundverse-demo/backend/logs/` | `tail -f backend/logs/app.log` |
| 前端服务 | 容器标准输出 | `docker-compose logs -f frontend-demo` |
| MySQL | 容器标准输出 | `docker-compose logs -f mysql` |
| Redis | 容器标准输出 | `docker-compose logs -f redis` |

### 备份策略

#### 数据库备份
部署脚本自动备份数据库，备份文件存储在本地 `./backups/` 目录:

```bash
# 查看备份文件
ls -lh backups/

# 手动备份数据库
ssh root@your-server-ip "docker exec SoundVerse-mysql mysqldump -u soundverse -ppassword soundverse > /tmp/backup_$(date +%Y%m%d).sql"

# 下载备份文件
scp root@your-server-ip:/tmp/backup_*.sql ./backups/
```

#### 代码备份
```bash
# 备份整个项目目录
tar -czf soundverse-backup-$(date +%Y%m%d).tar.gz --exclude=node_modules --exclude=__pycache__ .
```

### 日常维护任务

#### 清理无用镜像
```bash
# 清理未使用的Docker镜像
ssh root@your-server-ip "docker image prune -a -f"

# 清理停止的容器
ssh root@your-server-ip "docker container prune -f"
```

#### 更新基础镜像
```bash
# 拉取最新基础镜像
ssh root@your-server-ip "docker pull mysql:8.0"
ssh root@your-server-ip "docker pull redis:7-alpine"
```

## 故障排除

### 常见问题与解决方案

#### 1. 部署脚本失败

**问题**: `./deploy.sh` 执行失败
**排查步骤**:
```bash
# 1. 检查脚本语法
bash -n deploy.sh

# 2. 检查必要文件是否存在
ls -la .env docker-compose.yml frontend-demo/Dockerfile backend/Dockerfile.dev

# 3. 检查SSH连接
ssh root@your-server-ip "echo test"

# 4. 检查服务器Docker环境
ssh root@your-server-ip "docker --version && docker-compose --version"
```

#### 2. 服务启动失败

**问题**: 容器无法启动或健康检查失败
**排查步骤**:
```bash
# 查看容器日志
ssh root@your-server-ip "cd /opt/soundverse-demo && docker-compose logs"

# 检查端口冲突
ssh root@your-server-ip "netstat -tuln | grep -E ':8000|:5173|:3306|:6379'"

# 重启单个服务
ssh root@your-server-ip "cd /opt/soundverse-demo && docker-compose restart api"
```

#### 3. 前端无法访问后端API

**问题**: CORS错误或网络连接问题
**排查步骤**:
```bash
# 检查后端API是否可访问
curl -v http://your-server-ip:8000/health

# 检查前端配置
ssh root@your-server-ip "cat /opt/soundverse-demo/frontend-demo/.env"

# 检查防火墙规则
ssh root@your-server-ip "ufw status"
```

#### 4. 数据库连接失败

**问题**: MySQL连接错误
**排查步骤**:
```bash
# 检查MySQL容器状态
ssh root@your-server-ip "docker ps | grep mysql"

# 检查MySQL日志
ssh root@your-server-ip "docker logs SoundVerse-mysql"

# 进入MySQL容器测试连接
ssh root@your-server-ip "docker exec -it SoundVerse-mysql mysql -u soundverse -ppassword -e 'SHOW DATABASES;'"
```

#### 5. 磁盘空间不足

**问题**: 磁盘空间耗尽导致服务异常
**解决方案**:
```bash
# 查看磁盘使用情况
ssh root@your-server-ip "df -h"

# 清理Docker占用空间
ssh root@your-server-ip "docker system prune -a -f"

# 清理日志文件
ssh root@your-server-ip "find /opt/soundverse-demo/backend/logs -name '*.log' -mtime +7 -delete"
```

### 诊断工具

#### 健康检查脚本
创建诊断脚本 `diagnose.sh`:
```bash
#!/bin/bash
SERVER_IP=$1

echo "=== SoundVerse 服务诊断报告 ==="
echo "诊断时间: $(date)"
echo "目标服务器: $SERVER_IP"
echo ""

echo "1. 检查服务状态..."
ssh root@$SERVER_IP "cd /opt/soundverse-demo && docker-compose ps"

echo ""
echo "2. 检查网络连通性..."
curl -s -o /dev/null -w "前端: %{http_code}\n" http://$SERVER_IP:5173
curl -s -o /dev/null -w "后端健康检查: %{http_code}\n" http://$SERVER_IP:8000/health

echo ""
echo "3. 检查资源使用..."
ssh root@$SERVER_IP "free -h | grep Mem"
ssh root@$SERVER_IP "df -h /"
```

## 回滚流程

### 紧急回滚场景
1. **部署后服务不可用**: 新版本有严重bug
2. **数据库迁移失败**: 数据结构变更导致数据丢失
3. **性能严重下降**: 新版本性能不达标
4. **安全漏洞**: 发现严重安全风险

### 回滚准备

#### 1. 确认备份存在
```bash
# 检查数据库备份
ls -lh backups/

# 检查代码备份
ls -lh soundverse-backup-*.tar.gz
```

#### 2. 记录当前状态
```bash
# 记录当前版本
ssh root@your-server-ip "cd /opt/soundverse-demo && git log --oneline -5"

# 记录数据库状态
ssh root@your-server-ip "docker exec SoundVerse-mysql mysqldump -u soundverse -ppassword soundverse --no-data > /tmp/current_schema.sql"
```

### 完整回滚步骤

#### 方案一: 恢复到上一个备份版本 (推荐)
```bash
# 1. 停止当前服务
ssh root@your-server-ip "cd /opt/soundverse-demo && docker-compose down"

# 2. 恢复数据库备份
scp backups/最新的备份文件.sql root@your-server-ip:/tmp/restore.sql
ssh root@your-server-ip "docker exec -i SoundVerse-mysql mysql -u soundverse -ppassword soundverse < /tmp/restore.sql"

# 3. 恢复代码版本
# 如果使用Git，回退到上一个提交
ssh root@your-server-ip "cd /opt/soundverse-demo && git reset --hard HEAD~1"

# 4. 重启服务
ssh root@your-server-ip "cd /opt/soundverse-demo && docker-compose up -d"
```

#### 方案二: 使用完整备份恢复
```bash
# 1. 停止服务
ssh root@your-server-ip "cd /opt/soundverse-demo && docker-compose down"

# 2. 备份当前状态 (可选)
ssh root@your-server-ip "tar -czf /tmp/soundverse-failed-$(date +%Y%m%d).tar.gz /opt/soundverse-demo"

# 3. 删除当前部署
ssh root@your-server-ip "rm -rf /opt/soundverse-demo"

# 4. 重新部署上一个稳定版本
# 修改 deploy-config.json 中的代码版本或分支
# 运行部署脚本
./deploy.sh prod your-server-ip
```

#### 方案三: 仅回滚数据库
```bash
# 1. 恢复数据库
scp backups/最新的备份文件.sql root@your-server-ip:/tmp/restore.sql
ssh root@your-server-ip "docker exec -i SoundVerse-mysql mysql -u soundverse -ppassword soundverse < /tmp/restore.sql"

# 2. 重启后端服务
ssh root@your-server-ip "cd /opt/soundverse-demo && docker-compose restart api celery-worker celery-beat"
```

### 回滚验证
回滚完成后，必须验证系统状态:

```bash
# 1. 服务健康检查
curl -f http://your-server-ip:8000/health

# 2. 功能验证
# 测试核心功能: 音频上传、AI对话、语弹库浏览

# 3. 数据完整性检查
ssh root@your-server-ip "docker exec SoundVerse-mysql mysql -u soundverse -ppassword soundverse -e 'SELECT COUNT(*) FROM audio_segments;'"
```

### 回滚后处理
1. **记录回滚原因**: 在项目日志中记录回滚原因和版本
2. **问题分析**: 分析导致回滚的根本原因
3. **修复计划**: 制定问题修复和重新部署计划
4. **测试验证**: 在测试环境中充分验证修复版本

## 附录

### 部署脚本参数详解

#### deploy.sh 参数
```bash
./deploy.sh [环境] [服务器IP]
```
- **环境**: `dev` (开发) 或 `prod` (生产)，默认 `prod`
- **服务器IP**: 目标服务器公网IP，可从配置文件读取

#### update.sh 参数
```bash
./update.sh [服务器IP]
```
- **服务器IP**: 目标服务器公网IP，可从配置文件读取

### 配置文件详解
`deploy-config.json` 字段说明:

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `server_ip` | string | `"1.2.3.4"` | 目标服务器IP地址 |
| `app_name` | string | `"soundverse-demo"` | 应用名称，用于目录命名 |
| `backup_dir` | string | `"./backups"` | 本地备份目录路径 |
| `ssh_user` | string | `"root"` | SSH用户名 |
| `ssh_port` | number | `22` | SSH端口号 |
| `api_port` | number | `8000` | 后端API端口 |
| `frontend_port` | number | `5173` | 前端服务端口 |

### 常用命令速查

```bash
# 部署相关
./deploy.sh prod 1.2.3.4          # 完整部署
./update.sh 1.2.3.4               # 快速更新

# 服务器管理
ssh root@1.2.3.4                  # 连接到服务器
ssh root@1.2.3.4 "cd /opt/soundverse-demo && docker-compose ps"  # 查看服务状态

# 日志查看
ssh root@1.2.3.4 "cd /opt/soundverse-demo && docker-compose logs -f api"      # API日志
ssh root@1.2.3.4 "cd /opt/soundverse-demo && docker-compose logs -f frontend-demo"  # 前端日志

# 数据库操作
ssh root@1.2.3.4 "docker exec SoundVerse-mysql mysqldump -u soundverse -ppassword soundverse > backup.sql"  # 备份
ssh root@1.2.3.4 "docker exec -i SoundVerse-mysql mysql -u soundverse -ppassword soundverse < restore.sql"  # 恢复

# 服务控制
ssh root@1.2.3.4 "cd /opt/soundverse-demo && docker-compose restart"          # 重启所有服务
ssh root@1.2.3.4 "cd /opt/soundverse-demo && docker-compose down"             # 停止所有服务
ssh root@1.2.3.4 "cd /opt/soundverse-demo && docker-compose up -d"            # 启动所有服务
```

### 联系支持
如遇无法解决的问题，请:

1. **查看日志**: 收集相关服务日志
2. **记录错误**: 记录完整的错误信息和复现步骤
3. **环境信息**: 提供服务器环境和版本信息
4. **联系开发团队**: 提交Issue或联系项目维护者

---

**文档版本**: 1.0 (2026-04-06)
**适用版本**: SoundVerse 2.0 DEMO
**维护者**: SoundVerse 开发团队