# SoundVerse 后端服务

听听·原声态后端服务，基于 FastAPI 构建。

## 功能特性

- **用户认证**: 微信登录、JWT Token 管理
- **音频处理**: 上传、转码、分割、存储
- **语义检索**: 基于 FAISS 的音频片段语义匹配
- **AI 服务集成**: 阿里云 ASR/TTS/NLP API 集成
- **音频生成**: 模板化音频生成和分享
- **内容管理**: 平台音频库和用户内容管理

## 技术栈

- **Web 框架**: FastAPI
- **数据库**: MySQL + SQLAlchemy
- **缓存**: Redis
- **任务队列**: Celery + Redis
- **向量检索**: FAISS
- **AI 服务**: 阿里云智能语音交互 + 自然语言处理
- **音频处理**: pydub, librosa
- **容器化**: Docker + Docker Compose

## 快速开始

### 环境要求

- Python 3.11+
- MySQL 8.0+
- Redis 7.0+
- FFmpeg (音频处理)

### 安装步骤

1. **克隆项目**
   ```bash
   git clone <repository-url>
   cd backend
   ```

2. **创建虚拟环境**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   # 或
   .venv\Scripts\activate  # Windows
   ```

3. **安装依赖**
   ```bash
   pip install -e ".[dev]"
   ```

4. **环境配置**
   ```bash
   cp .env.example .env
   # 编辑 .env 文件，配置数据库、Redis、阿里云 API 等
   ```

5. **数据库初始化**
   ```bash
   alembic upgrade head
   ```

6. **启动服务**
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

### Docker 启动

```bash
docker-compose up -d
```

## 项目结构

```
backend/
├── main.py                    # 应用入口
├── config.py                  # 配置管理
├── pyproject.toml             # 项目配置和依赖
├── docker-compose.yml         # Docker 编排
├── shared/                    # 共享代码
│   ├── database/             # 数据库连接和模型
│   ├── models/               # SQLAlchemy 模型
│   ├── schemas/              # Pydantic 模型
│   └── utils/                # 工具函数
├── ai-models/                # AI 模型服务
│   ├── asr-service/          # 语音识别服务
│   ├── tts-service/          # 语音合成服务
│   ├── nlp-service/          # NLP 服务
│   └── audio-segmentation/   # 音频分割服务
├── api/                      # API 路由
│   ├── v1/                   # API v1 版本
│   │   ├── auth.py           # 认证相关
│   │   ├── audio.py          # 音频处理
│   │   ├── chat.py           # 聊天功能
│   │   └── generate.py       # 音频生成
│   └── __init__.py
├── services/                 # 业务服务层
│   ├── audio_service.py      # 音频服务
│   ├── chat_service.py       # 聊天服务
│   ├── search_service.py     # 搜索服务
│   └── user_service.py       # 用户服务
├── tasks/                    # Celery 任务
│   ├── audio_tasks.py        # 音频处理任务
│   └── ai_tasks.py           # AI 处理任务
├── infrastructure/           # 基础设施
│   ├── k8s/                  # Kubernetes 配置
│   ├── monitoring/           # 监控配置
│   └── logging/              # 日志配置
├── tests/                    # 测试文件
└── scripts/                  # 部署脚本
```

## API 文档

启动服务后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 开发指南

### 代码规范

- 使用 `black` 格式化代码
- 使用 `ruff` 进行代码检查
- 使用 `mypy` 进行类型检查

### 预提交钩子

安装预提交钩子：
```bash
pre-commit install
```

### 测试

运行测试：
```bash
pytest
```

运行特定测试：
```bash
pytest tests/test_auth.py -v
```

### 数据库迁移

创建新迁移：
```bash
alembic revision --autogenerate -m "描述"
```

应用迁移：
```bash
alembic upgrade head
```

## 部署

### 生产环境

1. **构建 Docker 镜像**
   ```bash
   docker build -t soundverse-backend:latest .
   ```

2. **运行容器**
   ```bash
   docker run -d \
     --name soundverse-backend \
     -p 8000:8000 \
     --env-file .env.production \
     soundverse-backend:latest
   ```

### Kubernetes

参考 `infrastructure/k8s/` 目录下的配置文件。

## 配置说明

### 环境变量

关键环境变量：

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `DATABASE_URL` | MySQL 数据库连接 | `mysql://user:pass@localhost:3306/soundverse` |
| `REDIS_URL` | Redis 连接 | `redis://localhost:6379/0` |
| `ALIYUN_ACCESS_KEY_ID` | 阿里云 Access Key ID | |
| `ALIYUN_ACCESS_KEY_SECRET` | 阿里云 Access Key Secret | |
| `JWT_SECRET_KEY` | JWT 密钥 | `your-secret-key` |
| `OSS_ENDPOINT` | 阿里云 OSS 端点 | `oss-cn-hangzhou.aliyuncs.com` |
| `OSS_BUCKET` | OSS 存储桶名称 | `soundverse-audio` |

### 阿里云 API 配置

需要开通的服务：
- 智能语音交互（ASR/TTS）
- 自然语言处理（NLP）
- 对象存储 OSS

## 监控和日志

- 使用 Prometheus 进行指标监控
- 日志输出到文件和控制台
- 关键业务指标监控

## 许可证

MIT License