# CLAUDE.md

本文件为 SoundVerse 项目提供核心指引，请在使用 Claude Code 时参考。保持内容简洁、可操作。

## 项目概览

SoundVerse（听听·原声态）是北京广电音频媒资 AI 活化项目。核心目标：AI 重构广播节目为颗粒化音频片段，建立声音库，支持智能交互与生成。

### 当前项目结构
```
SoundVerse/
├── wechat-miniprogram/          # 微信小程序前端 (TypeScript, Vant Weapp)
├── backend/                     # Python 后端 (FastAPI, MySQL, Redis, Celery)
├── admin/                       # React 管理后台 (已容器化，运行于 5173 端口)
└── CLAUDE.md                    # 本文件
```

## 环境与启动

### Docker 开发环境（全容器化）
```bash
cd backend
docker-compose up -d              # 启动所有服务 (api, admin, mysql, redis)
docker-compose ps                 # 查看服务状态
docker-compose logs -f api        # 查看 API 日志
docker-compose down               # 停止所有服务
docker-compose up -d --build      # 重新构建并启动
```

### 后端开发
```bash
cd backend
pip install -e ".[dev]"           # 安装依赖（开发模式）
python -m scripts.start_dev.sh    # 启动开发环境
alembic upgrade head              # 执行数据库迁移
pytest                            # 运行测试（待实现）
```

### 微信小程序
```bash
cd wechat-miniprogram
npm install                       # 安装依赖
npm run build                     # 构建 TypeScript
# 使用微信开发者工具进行预览、调试、上传
```

### 批量操作脚本
```bash
cd backend
python -m scripts.mass_ingest      # 批量音频入库
python -m scripts.sync_dashvector  # 同步向量到 DashVector
python -m scripts.audit_db         # 数据库完整性审计
```

### 数据库备份与恢复
```bash
# 备份
docker exec SoundVerse-mysql mysqldump -u soundverse -ppassword soundverse > backup.sql

# 恢复
docker exec -i SoundVerse-mysql mysql -u soundverse -ppassword soundverse < backup.sql
```

## 核心业务规则（不可变真理）

### 音频处理规则
- **硬切时长**：音频片段严格限制在 **2‑8 秒**（`MIN_SEGMENT_DURATION=2.0`, `MAX_SEGMENT_DURATION=8.0`）
- **采样率**：16kHz 单声道（`AUDIO_SAMPLE_RATE=16000`, `AUDIO_CHANNELS=1`）
- **静音检测**：`MIN_SILENCE_LEN=500ms`, `SILENCE_THRESH=-40dB`

### 向量与语义搜索配置
- **向量维度**：V4 文本嵌入维度为 **1024**（`VECTOR_DIMENSION=1024`）
- **语义相似度门槛**：`SIMILARITY_THRESHOLD=0.25`（基础匹配门槛）
- **音频回复门槛**（配置于 `.env`）：
  - `AUDIO_REPLY_THRESHOLD=0.55`（直接播放）
  - `AUDIO_SUGGEST_THRESHOLD=0.35`（建议播放）
- **搜索候选数**：`SEARCH_TOP_K=5`（每次搜索返回5个候选）

### 容器命名规范
- 所有 Docker 容器均以 `SoundVerse-` 开头（例如 `SoundVerse-api`, `SoundVerse-admin`）
- Docker 网络：`SoundVerse-network`
- Admin 前端访问地址：`http://localhost:5173`（通过 nginx 反向代理至后端 API）

## 代码规范

### 目录结构约定
- `backend/api/v1/`：API 路由（认证、音频、聊天、生成）
- `backend/services/`：业务逻辑服务
- `backend/shared/`：数据库模型、数据模式、工具函数
- `backend/ai‑models/`：AI 服务集成
- `backend/scripts/`：运维脚本
- `wechat‑miniprogram/src/pages/`：小程序页面
- `wechat‑miniprogram/src/services/`：前端 API 服务
- `admin/src/pages/`：管理后台页面

### 命名规范
- **Python**：变量/函数使用 snake_case，类使用 PascalCase
- **TypeScript**：变量/函数使用 camelCase，组件/接口使用 PascalCase
- **数据库表名**：复数 snake_case（例如 `audio_segments`, `chat_sessions`）
- **API 端点**：RESTful，kebab‑case（例如 `/api/v1/audio‑segments`）

### 开发实践
- **类型提示**：所有 Python 函数必须添加类型提示
- **错误处理**：使用结构化日志，绝不暴露内部错误信息
- **配置管理**：仅使用环境变量，绝不硬编码密钥
- **依赖管理**：后端通过 `pyproject.toml`，前端通过 `package.json`

## 重要说明

### 管理后台（Admin）
- 已容器化，通过 nginx 反向代理连接后端 API
- 前端 API 请求路径为 `/api/` → 代理至 `api:8000`
- 技术栈：React + TypeScript + Ant Design
- Docker Compose 运行时可访问 `http://localhost:5173`

### 微信集成
- 使用官方微信登录流程
- AppID 与 AppSecret 配置于 `.env`
- 用户令牌通过 Redis 缓存安全存储

### AI 服务集成
- 阿里云 ASR 用于语音转文本
- DashScope（V4 模型）用于文本嵌入生成
- 向量搜索通过 DashVector 或 FAISS 实现
- 已实现速率限制与缓存机制

### 监控与日志
- Prometheus 指标端点：`/metrics`
- 健康检查端点：`/health`
- 结构化日志，支持日志级别配置
- Grafana 监控服务已在 docker‑compose 中注释（可选）

---

**最后更新**：2026‑03‑22
