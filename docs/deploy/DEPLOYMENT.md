# SoundVerse 部署与维护指南

本文档提供 SoundVerse 2.0 DEMO 版本的部署、更新、监控和维护说明。

## 环境信息

### 服务器信息
- **公网IP**: 123.57.81.79
- **域名**: https://soundverse.vbegin.com.cn
- **服务器**: Alibaba Cloud Linux 4 LTS 64位
- **项目目录**: `/opt/soundverse/`

### 服务端口
| 端口 | 服务 | 访问方式 |
|------|------|----------|
| 8000 | 后端 API | SLB 转发 |
| 5173 | 前端 | SLB 转发 |

---

## 部署架构

```
客户端 → SLB → ECS:5173 (前端) → Nginx代理 → API:8000
                    ↓
              ECS:8000 (后端API)
                    ↓
              Docker容器 (MySQL, Redis)
```

### 容器列表
| 容器名 | 镜像 | 功能 |
|--------|------|------|
| SoundVerse-api | soundverse-api | API服务 + Gunicorn |
| SoundVerse-celery-worker | soundverse-api | 异步任务处理 |
| SoundVerse-celery-beat | soundverse-api | 定时任务调度 |
| SoundVerse-frontend-demo | soundverse-frontend-demo | 前端Vue应用 |
| SoundVerse-mysql | mysql:8.0 | MySQL数据库 |
| SoundVerse-redis | redis:7-alpine | Redis缓存 |

---

## 首次部署

### 方式一：服务器源码构建 + 热重载（推荐开发阶段）

**特点**：代码修改后自动热重载，适合快速迭代开发

1. 上传项目源码到服务器：
```bash
# 使用WinSCP上传整个项目到 /opt/soundverse/
```

2. 配置并启动：
```bash
cd /opt/soundverse

# 启动所有服务（支持热重载）
docker-compose -f docker-compose.prod.yml up -d

# 开启文件监视（保持运行）
docker-compose -f docker-compose.prod.yml watch
```

3. 验证服务：
```bash
curl http://localhost:8000/health
curl http://localhost:5173
```

**热重载说明**：
- 前端源码修改后自动同步到容器
- 后端 Python 代码修改后自动重载（uvicorn --reload）
- Celery Worker/Beat 不支持热重载，代码修改后需重启

### 方式二：本地构建镜像上传

**特点**：服务器带宽要求低，但每次更新需重新构建

1. 本地构建镜像：
```bash
cd D:/GitHub/SoundVerse

# 构建后端镜像
docker build -f backend/Dockerfile.prod -t soundverse-api:prod ./backend
docker save soundverse-api:prod -o D:/soundverse-api.tar

# 构建前端镜像
docker build -f frontend-demo/Dockerfile.prod -t soundverse-frontend:prod ./frontend-demo
docker save soundverse-frontend:prod -o D:/soundverse-frontend.tar
```

2. 上传到服务器：
```bash
# WinSCP上传 tar 文件到 /opt/soundverse/
```

3. 服务器加载：
```bash
cd /opt/soundverse

# 加载镜像
docker load -i soundverse-api.tar
docker load -i soundverse-frontend.tar

# 启动服务
docker-compose -f docker-compose.prod.yml up -d
```

---

## 数据库同步

### 导出本地数据库
```bash
# Windows本地执行
docker cp soundverse-mysql:/tmp/soundverse.sql D:/soundverse_new.sql

# 如果/tmp没有，手动导出
docker exec soundverse-mysql mysqldump -u root -prootpassword --default-character-set=utf8mb4 --result-file=/tmp/soundverse.sql soundverse
docker cp soundverse-mysql:/tmp/soundverse.sql D:/soundverse_new.sql
```

### 导入到服务器
```bash
cd /opt/soundverse

# 重建数据库
docker exec SoundVerse-mysql mysql -u root -prootpassword -e "DROP DATABASE IF EXISTS soundverse; CREATE DATABASE soundverse CHARACTER SET utf8mb4;"

# 导入数据
docker exec -i SoundVerse-mysql mysql -u root -prootpassword --default-character-set=utf8mb4 soundverse < soundverse_new.sql

# 验证
docker exec SoundVerse-mysql mysql -u root -prootpassword -e "USE soundverse; SHOW TABLES;"
```

---

## 常用维护命令

### 服务控制
```bash
# 查看所有容器状态
docker ps

# 重启所有服务
docker-compose -f docker-compose.prod.yml restart

# 重启特定服务
docker-compose -f docker-compose.prod.yml restart api
docker-compose -f docker-compose.prod.yml restart frontend-demo

# 停止所有服务
docker-compose -f docker-compose.prod.yml down

# 查看日志
docker logs SoundVerse-api -f
docker logs SoundVerse-frontend-demo -f
docker logs SoundVerse-celery-worker -f
docker logs SoundVerse-celery-beat -f
```

### 数据库操作
```bash
# 重置用户每日聊天次数
docker exec SoundVerse-mysql mysql -u root -prootpassword -e "USE soundverse; UPDATE users SET daily_chat_count = 0;"

# 查看节目状态
docker exec SoundVerse-mysql mysql -u root -prootpassword -e "USE soundverse; SELECT id, title, processing_status FROM audio_sources;"

# 重置卡住的节目
docker exec SoundVerse-mysql mysql -u root -prootpassword -e "USE soundverse; UPDATE audio_sources SET processing_status='pending' WHERE id='替换为节目ID';"
```

### 手动执行重置任务
```bash
# 手动重置每日计数
docker exec SoundVerse-api python -c "
import asyncio
from database import AsyncSessionLocal
from services.user_service import reset_daily_counts

async def main():
    async with AsyncSessionLocal() as db:
        await reset_daily_counts(db)
    print('每日计数已重置')

asyncio.run(main())
"
```

---

## 环境配置说明

### 前端环境区分

| 文件 | VITE_APP_MODE | 效果 |
|------|---------------|------|
| `.env` | `demo` | 开发模式，预置账号密码，可一键登录 |
| `.env.production` | `production` | 生产模式，无预置账号，需输入凭据 |

### 后端环境区分

| 环境 | ENVIRONMENT | 效果 |
|------|-------------|------|
| 开发 | `development` | 跳过聊天次数限制 |
| 生产 | `production` | 每日50次聊天限制 |

---

## 防火墙配置 (Alibaba Cloud Linux)

```bash
# 开放端口
iptables -I INPUT -p tcp --dport 8000 -j ACCEPT
iptables -I INPUT -p tcp --dport 5173 -j ACCEPT

# 保存规则
service iptables save
```

**注意**：还需在阿里云 ECS 安全组中开放 8000 和 5173 端口入站规则。

---

## SLB 配置

### 监听规则
| 协议 | SLB端口 | 后端端口 | 健康检查 |
|------|---------|---------|----------|
| HTTP | 80 | 5173 | `/` |
| HTTP | 8000 | 8000 | `/api/health` |

### 域名解析
- `soundverse.vbegin.com.cn` → SLB 公网 IP

---

## 故障排除

### 1. 服务无法启动
```bash
# 查看日志
docker-compose -f docker-compose.prod.yml logs

# 检查容器状态
docker ps -a
```

### 2. 数据库连接失败
```bash
# 检查MySQL是否运行
docker exec SoundVerse-mysql mysql -u root -prootpassword -e "SHOW DATABASES;"
```

### 3. 前端 CORS 错误
检查 `.env` 配置：
```bash
# 查看服务器上的CORS配置
docker exec SoundVerse-api env | grep CORS
```

### 4. 音频播放失败
```bash
# 检查OSS链接
curl -I "https://ai-sun-vbegin-com-cn.oss-cn-beijing.aliyuncs.com/audio/segments/xxx.mp3"
```

### 5. 聊天次数超限
```bash
# 重置每日计数
docker exec SoundVerse-mysql mysql -u root -prootpassword -e "USE soundverse; UPDATE users SET daily_chat_count = 0;"
```

---

## 更新流程

### 方式一：热重载（开发阶段）
修改代码后，Docker 自动检测并重载。

### 方式二：手动重启
```bash
# 修改代码后
docker-compose -f docker-compose.prod.yml restart api celery-worker celery-beat
```

### 方式三：重新构建镜像
```bash
# 本地重新构建
docker build -f backend/Dockerfile.prod -t soundverse-api:prod ./backend
docker save soundverse-api:prod -o D:/soundverse-api.tar

# 上传并加载
docker load -i soundverse-api.tar
docker-compose -f docker-compose.prod.yml up -d --build
```

---

## 备份策略

### 数据库备份
```bash
# 导出
docker exec SoundVerse-mysql mysqldump -u root -prootpassword --default-character-set=utf8mb4 soundverse > backup_$(date +%Y%m%d).sql
```

### 关键文件
- `/opt/soundverse/backend/data/faiss_index.bin` - 向量索引
- `/opt/soundverse/backend/data/uploads/` - 上传音频
- `/opt/soundverse/backend/data/auto_import/` - 导入数据

---

## 每日重置任务

Celery Beat 已配置每日凌晨 0 点自动重置用户聊天次数。

### 检查 Beat 是否运行
```bash
docker logs SoundVerse-celery-beat --tail 10
```

### 预期日志
```
[celery.beat:MainThread] Scheduler: Sending due task reset_daily_counts
```

---

## 文档版本

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0 | 2026-04-06 | 初始版本 |
| 2.0 | 2026-04-22 | 更新部署方式，新增热重载配置 |

---

**适用版本**: SoundVerse 2.0 DEMO
**最后更新**: 2026-04-22
