# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在本代码库中工作时提供指引。

## 项目概览

SoundVerse（听听·原声态）是北京广电音频媒资 AI 活化项目。核心目标：使用 AI 将广播节目重构为颗粒化的音频片段，建立声音库，支持智能交互与生成。

## 项目结构

```
SoundVerse/
├── frontend-demo/               # React DEMO 前端 (Vite + TypeScript)
│   ├── src/
│   │   ├── pages/               # 核心页面
│   │   │   ├── UploadStudio.tsx       # 音频工坊（上传与裁切）
│   │   │   ├── Library.tsx            # 精选语弹库（管理片段）
│   │   │   └── AILab.tsx              # AI 对话实验室
│   │   ├── components/          # 公共组件
│   │   │   ├── AudioPlayer.tsx        # 音频播放器
│   │   │   ├── Auth.tsx               # 认证组件
│   │   │   └── Layout.tsx             # 主布局
│   │   ├── contexts/            # React Context
│   │   │   └── AuthContext.tsx        # 认证状态管理
│   │   ├── lib/                 # 工具库
│   │   │   └── supabase.ts            # Supabase 客户端配置
│   │   └── App.tsx              # 应用根组件
│   ├── supabase/migrations/     # 数据库迁移脚本
│   ├── package.json             # 依赖管理
│   ├── Dockerfile               # 生产环境 Docker 配置
│   └── vite.config.ts           # Vite 构建配置
├── backend/                     # Python 后端 (FastAPI)
│   ├── api/v1/                  # API 路由
│   │   ├── auth.py              # 认证（微信登录、JWT）
│   │   ├── audio.py             # 音频上传、处理、查询
│   │   ├── chat.py              # 聊天交互、语义匹配
│   │   └── generate.py          # 音频生成
│   ├── services/                # 业务逻辑服务
│   │   ├── audio_processing_service.py  # 音频分割、ASR 识别
│   │   ├── audio_generation_service.py  # TTS 合成、音频混音
│   │   ├── chat_service.py              # 聊天会话管理
│   │   ├── search_service.py            # DashVector 语义搜索
│   │   ├── prompt_generation_service.py # LLM 提示词生成
│   │   └── storage_service.py           # OSS 文件存储
│   ├── ai_models/               # AI 模型集成
│   │   ├── asr_service.py       # 阿里云 ASR（语音识别）
│   │   ├── nlp_service.py       # DashScope 文本嵌入
│   │   └── llm_service.py       # DashScope 大语言模型
│   ├── shared/                  # 共享代码
│   │   ├── database/            # 数据库会话管理
│   │   ├── models/              # SQLAlchemy 模型 (User, AudioSource, AudioSegment 等)
│   │   ├── schemas/             # Pydantic 数据模式
│   │   └── utils/               # 工具函数（日志等）
│   ├── scripts/                 # 运维脚本
│   ├── config.py                # 应用配置（Settings 类）
│   ├── main.py                  # 应用入口
│   ├── pyproject.toml           # 项目依赖和工具配置
│   └── .env.example             # 环境变量模板
├── README.md                    # 项目总览
├── backend/README.md            # 后端详细文档
├── docker-compose.yml           # Docker 编排配置
└── CLAUDE.md                    # 本文件
```

**注意**：
- `frontend-demo/` 是当前的 DEMO 前端，使用 Supabase 作为后端数据库（独立于 Python 后端）
- `archive/admin/` 和 `archive/wechat-miniprogram/` 包含旧代码，除非明确要求，否则请勿引用这些目录

## 常用开发命令

### 前端开发（frontend-demo）

```bash
cd frontend-demo

# 安装依赖
npm install

# 本地开发（热更新）
npm run dev

# 构建生产版本
npm run build

# 预览生产构建
npm run preview

# 代码检查
npm run lint

# 类型检查
npm run typecheck
```

### 后端开发

```bash
cd backend

# 安装依赖（开发模式）
pip install -e ".[dev]"

# 运行本地开发服务器
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 数据库迁移（如果配置了 alembic）
alembic upgrade head
alembic revision --autogenerate -m "描述"

# 代码质量工具
black .                          # 代码格式化
ruff check .                     # 代码检查
mypy .                           # 类型检查
pre-commit run --all             # 运行所有预提交钩子

# 测试命令（tests 目录尚未创建）
pytest                           # 运行所有测试
pytest tests/test_auth.py -v     # 运行特定测试文件
pytest -m "not slow"             # 跳过慢速测试
```

### Docker 开发环境

```bash
# 构建并启动所有服务（包括 frontend-demo 和 backend）
docker-compose up -d

# 查看服务状态
docker-compose ps

# 仅启动前端
docker-compose up -d frontend-demo

# 仅启动后端服务
docker-compose up -d api celery-worker celery-beat

# 前端访问地址
# http://localhost:5173

# 后端 API 地址
# http://localhost:8000/docs

# 查看日志
docker-compose logs -f frontend-demo
docker-compose logs -f api
docker-compose logs -f celery-worker

# 重启前端服务
docker-compose restart frontend-demo

# 重新构建前端镜像
docker-compose build frontend-demo

# 停止所有服务
docker-compose down

# 停止并删除数据卷
docker-compose down -v
```

### 批量操作脚本

```bash
cd backend

# 批量音频入库
python -m scripts.mass_ingest

# 同步向量到 DashVector
python -m scripts.sync_dashvector

# 数据库完整性审计
python -m scripts.audit_db

# 处理完整音频流程
python -m scripts.process_full_pipeline
```

## 架构概览

### 核心业务流程

**1. 音频入库流程**
```
上传 → 格式验证 → 上传至 OSS → 创建 AudioSource
→ Celery 任务：分割（静音检测）→ ASR 识别
→ 文本嵌入（DashScope）→ 创建 AudioSegment → 在 DashVector 中索引
```

**2. 语义搜索流程**
```
用户查询 → 文本嵌入 → DashVector 相似度搜索
→ 按 SIMILARITY_THRESHOLD (0.25) 过滤 → 返回前 SEARCH_TOP_K (5) 个结果
→ 应用 AUDIO_REPLY_THRESHOLD (0.55) 决定是否播放
```

**3. 音频生成流程**
```
选择模板 → 填充变量 → LLM 生成脚本
→ TTS 合成 → 与背景音乐混合 → 生成最终音频
```

### DEMO 前端架构（frontend-demo）

**技术栈**：
- **框架**：React 18 + TypeScript + Vite
- **UI 组件库**：lucide-react (图标)
- **样式**：TailwindCSS
- **数据库**：Supabase (PostgreSQL + RLS)
- **部署**：Docker 容器

**核心页面**：
- `UploadStudio.tsx`：音频工坊 - 上传音频文件，选择裁切策略（短句/段落/对话），生成语弹片段
- `Library.tsx`：精选语弹库 - 浏览、搜索、过滤和管理音频片段，支持按情绪、标签、关键词筛选
- `AILab.tsx`：AI 对话实验室 - 与 AI 聊天，获取带音频的回复，支持话题推荐

**数据模型**（Supabase 迁移）：
- `audio_clips` 表：存储用户上传的音频片段，包含转录文本、情绪标签、内容标签
- `conversations` 表：存储对话记录，区分 user/assistant 角色

**认证流程**：
- 使用 Supabase Auth 实现用户注册和登录
- Row Level Security (RLS) 确保用户只能访问自己的数据

### 数据库结构

| 表名 | 关键字段 | 关系 |
|------|---------|------|
| `users` | id, wechat_openid, nickname | 拥有 audio_segments, chat_sessions, favorites |
| `audio_sources` | id, title, oss_key, processing_status | 拥有多个 audio_segments |
| `audio_segments` | id, source_id, transcription, vector, review_status | 属于 source/user，拥有 favorites/messages |
| `chat_sessions` | id, user_id, title | 拥有多个 chat_messages |
| `chat_messages` | id, session_id, content, segment_id | 属于 session/segment |
| `favorite_segments` | user_id, segment_id | 用户收藏片段的关联表 |

### 服务层职责

- **`audio_processing_service.py`**：使用静音检测进行音频分割，ASR 集成
- **`audio_generation_service.py`**：TTS 合成，与背景音乐混音
- **`chat_service.py`**：聊天会话生命周期，消息历史，语义匹配
- **`search_service.py`**：DashVector 向量搜索，相似度过滤
- **`prompt_generation_service.py`**：基于 LLM 的提示词生成，用于对话上下文
- **`storage_service.py`**：OSS 文件上传/下载操作

### AI 模型集成

- **ASR 服务** ([ai_models/asr_service.py](backend/ai_models/asr_service.py))：阿里云智能语音交互，用于语音转文本
- **NLP 服务** ([ai_models/nlp_service.py](backend/ai_models/nlp_service.py))：DashScope text-embedding-v4（1024 维向量）
- **LLM 服务** ([ai_models/llm_service.py](backend/ai_models/llm_service.py))：DashScope 大语言模型，用于提示词生成

## 核心业务规则（代码定义的常量）

### 音频处理
- **片段时长**：严格限制在 **2-8 秒**（`MIN_SEGMENT_DURATION=2.0`，`MAX_SEGMENT_DURATION=8.0`）
- **采样率**：16kHz 单声道（`AUDIO_SAMPLE_RATE=16000`，`AUDIO_CHANNELS=1`）
- **静音检测**：`MIN_SILENCE_LEN=500ms`，`SILENCE_THRESH=-40dB`
- **保留静音**：片段周围保留 200ms 静音

### 语义搜索配置
- **向量维度**：**1024**（text-embedding-v4 模型）
- **相似度门槛**：`SIMILARITY_THRESHOLD=0.25`（基础匹配门槛）
- **搜索候选数**：每次查询返回 `SEARCH_TOP_K=5` 个结果
- **音频回复门槛**：`AUDIO_REPLY_THRESHOLD=0.55`（直接播放音频）
- **音频建议门槛**：`AUDIO_SUGGEST_THRESHOLD=0.35`（建议播放音频）

### 处理状态

**AudioSource processing_status**：
- `pending` → `processing` → `completed` / `failed`

**AudioSegment review_status**：
- `pending` → `approved` / `rejected`

## 配置管理

所有配置通过 `.env` 文件中的环境变量管理（从 `.env.example` 复制）：

```bash
# 复制模板
cp .env.example .env
# 编辑为实际值
```

[config.py](backend/config.py) 中的关键配置部分：
- 应用设置（主机、端口、环境）
- 安全（JWT 密钥、算法）
- 数据库（MySQL 连接、连接池大小）
- Redis（缓存和 Celery 消息队列）
- 阿里云服务（ASR、OSS、DashScope）
- DashVector（向量数据库端点、API 密钥）
- 音频处理参数
- 速率限制和缓存

## 开发实践

### Python 代码规范
- **类型提示**：所有函数必须添加（由 mypy 强制执行）
- **命名**：变量/函数使用 snake_case，类使用 PascalCase
- **表名**：复数 snake_case（例如 `audio_segments`）
- **API 端点**：RESTful，kebab-case（例如 `/api/v1/audio-segments`）

### 错误处理
- 通过 [shared/utils/logging.py](backend/shared/utils/logging.py) 使用结构化日志
- 绝不向客户端暴露内部错误详情
- [main.py](backend/main.py) 中的全局异常处理

### 安全性
- 所有密钥通过环境变量管理（绝不硬编码）
- 使用 JWT 令牌进行认证（HS256 算法）
- 仅对开发环境配置 CORS
- API 端点启用速率限制

## 监控和可观测性

- **健康检查**：
  - 后端：`GET /health` 或 `GET /api/health`
  - 前端：Docker 内置 healthcheck (http://localhost:5173)
- **Prometheus 指标**：后端 `/metrics` 端点
- **API 文档**：后端 Swagger UI（`/docs`）
- **日志**：后端结构化日志输出到 `logs/soundverse.log`

## 关键文件参考

- **配置**：[backend/config.py](backend/config.py)
- **应用入口**：[backend/main.py](backend/main.py)
- **API 路由**：[backend/api/v1/](backend/api/v1/)
- **服务**：[backend/services/](backend/services/)
- **模型**：[backend/shared/models/](backend/shared/models/)
- **环境变量模板**：[backend/.env.example](backend/.env.example)
- **前端入口**：[frontend-demo/src/App.tsx](frontend-demo/src/App.tsx)
- **前端页面**：[frontend-demo/src/pages/](frontend-demo/src/pages/)
- **Supabase 配置**：[frontend-demo/src/lib/supabase.ts](frontend-demo/src/lib/supabase.ts)
- **Docker 编排**：[docker-compose.yml](docker-compose.yml)
- **前端 Dockerfile**：[frontend-demo/Dockerfile](frontend-demo/Dockerfile)
