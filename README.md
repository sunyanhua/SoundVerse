# SoundVerse - 听听·原声态

[![健康检查](https://img.shields.io/badge/健康检查-优秀-success?style=flat-square)](项目健康检查报告.md)
[![Python](https://img.shields.io/badge/Python-3.11+-blue?style=flat-square)](backend/)
[![FastAPI](https://img.shields.io/badge/FastAPI-最新版-009688?style=flat-square)](backend/)
[![React](https://img.shields.io/badge/React-18+-61dafb?style=flat-square)](frontend-demo/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5+-007acc?style=flat-square)](frontend-demo/)
[![2.0 DEMO](https://img.shields.io/badge/2.0_DEMO-开发中-orange?style=flat-square)](docs/tasks/2.0DEMO版/2.0DEMO版最终执行方案.md)

AI 驱动的"声音百科+社交语库"项目。通过 AI 技术对广播节目进行颗粒化重构，建立声音库，实现智能音频交互与生成。

**当前阶段**: 2.0 DEMO 版开发，专注于核心功能精简与一键部署。

---

## 📖 项目概述

**听听·原声态**是一个创新的音频交互平台，核心功能包括：

- 🎯 **智能音频库**: 将广播节目拆分为 2-8 秒的语义片段
- 🤖 **AI 对话**: 用真实的广播音频片段回答用户问题
- 🎨 **音频生成**: 创建祝福、表白、道歉等定制化音频
- 🔍 **语义搜索**: 基于 1024 维向量的精准匹配

---

## 🚀 快速开始

### ✅ 环境检查

项目已通过健康检查，综合评分 **9.5/10**，可立即开始开发。

**详细检查报告**: [项目健康检查报告](项目健康检查报告.md)

### 🔧 启动服务

#### 1. 启动后端 (FastAPI)
```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
**访问**: http://localhost:8000/docs (Swagger UI)

#### 2. 启动前端 (React DEMO)
```bash
cd frontend-demo
npm run dev
```
**访问**: http://localhost:5173

#### 3. 验证服务
```bash
curl http://localhost:8000/health
```
**预期**: `{"status":"healthy","services":{"database":"connected","dashvector":"connected","redis":"connected"}}`

### 🐳 Docker 启动（可选）
```bash
docker-compose up -d
```

---

## 📁 项目结构

```
SoundVerse/
├── frontend-demo/               # React DEMO 前端
│   ├── src/
│   │   ├── pages/              # 核心页面
│   │   │   ├── UploadStudio.tsx       # 音频工坊（上传与裁切）
│   │   │   ├── Library.tsx            # 精选语弹库（管理片段）
│   │   │   └── AILab.tsx              # AI 对话实验室
│   │   ├── components/         # 公共组件
│   │   ├── contexts/           # React Context
│   │   ├── lib/                # 工具库（Supabase）
│   │   └── App.tsx             # 应用入口
│   ├── supabase/migrations/    # 数据库迁移脚本
│   ├── package.json            # 依赖管理
│   ├── Dockerfile              # Docker 配置
│   └── vite.config.ts          # 构建配置
│
├── backend/                    # Python 后端 (FastAPI)
│   ├── api/v1/                 # API 路由
│   │   ├── auth.py             # 认证（微信登录、JWT）
│   │   ├── audio.py            # 音频上传、处理、查询
│   │   ├── chat.py             # 聊天交互、语义匹配
│   │   └── generate.py         # 音频生成
│   ├── services/               # 业务逻辑服务
│   │   ├── audio_processing_service.py  # 音频分割、ASR 识别
│   │   ├── audio_generation_service.py  # TTS 合成、音频混音
│   │   ├── chat_service.py              # 聊天会话管理
│   │   ├── search_service.py            # DashVector 语义搜索
│   │   ├── prompt_generation_service.py # LLM 提示词生成
│   │   └── storage_service.py           # OSS 文件存储
│   ├── ai_models/              # AI 模型集成
│   │   ├── asr_service.py      # 阿里云 ASR（语音识别）
│   │   ├── nlp_service.py      # DashScope 文本嵌入
│   │   └── llm_service.py      # DashScope 大语言模型
│   ├── shared/                 # 共享代码
│   │   ├── database/           # 数据库会话管理
│   │   ├── models/             # SQLAlchemy 模型
│   │   ├── schemas/            # Pydantic 数据模式
│   │   └── utils/              # 工具函数
│   ├── config.py               # 应用配置
│   ├── main.py                 # 应用入口
│   ├── pyproject.toml          # 依赖配置
│   └── .env.example            # 环境变量模板
│
├── docker-compose.yml          # Docker 编排配置
├── README.md                   # 本文件
├── CLAUDE.md                   # Claude Code 项目指南
└── 项目健康检查报告.md          # 健康检查报告
```

---

## 🔧 技术栈

### 后端 (Python)
- **Web 框架**: FastAPI (高性能异步框架)
- **数据库**: MySQL (生产) / SQLite (开发)
- **缓存**: Redis (会话管理、Celery 消息队列)
- **任务队列**: Celery (异步音频处理)
- **向量检索**: DashVector (1024 维语义向量)
- **AI 服务**: 
  - 阿里云智能语音交互 (ASR/TTS)
  - DashScope (文本嵌入、大语言模型)

### 前端 (React DEMO)
- **框架**: React 18 + TypeScript
- **构建工具**: Vite
- **UI 组件**: lucide-react (图标)
- **样式**: TailwindCSS
- **数据库**: Supabase (PostgreSQL + RLS)
- **状态管理**: React Context

### 基础设施
- **对象存储**: 阿里云 OSS
- **容器编排**: Docker + Docker Compose
- **CI/CD**: 待配置

---

## 🎯 核心功能

### 1. 音频入库流程
```
上传音频 → 格式验证 → 上传至 OSS → 静音分割 (2-8 秒)
→ ASR 识别 (阿里云) → 文本嵌入 (DashScope 1024 维)
→ 创建 AudioSegment → 在 DashVector 中索引
```

### 2. 语义搜索流程
```
用户查询 → 文本嵌入 → DashVector 相似度搜索
→ 按相似度阈值 (0.25) 过滤 → 返回前 5 个结果
→ 按音频回复阈值 (0.55) 决定是否播放
```

### 3. 音频生成流程
```
选择模板 → 填充变量 → LLM 生成脚本
→ TTS 合成 (阿里云) → 与背景音乐混合
→ 生成最终音频 → 用户下载/分享
```

---

## 📊 数据库设计

### 后端数据库 (MySQL)
| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `users` | 用户信息 | id, wechat_openid, nickname |
| `audio_sources` | 原始音频 | id, title, oss_key, processing_status |
| `audio_segments` | 音频片段 | id, source_id, transcription, vector, review_status |
| `chat_sessions` | 聊天会话 | id, user_id, title |
| `chat_messages` | 聊天消息 | id, session_id, content, segment_id |
| `favorite_segments` | 收藏片段 | user_id, segment_id |

### 前端数据库 (Supabase)
| 表名 | 说明 |
|------|------|
| `audio_clips` | 用户上传的音频片段 |
| `conversations` | 对话记录 |

---

## 🛠️ 常用命令

### 后端开发
```bash
cd backend

# 安装依赖
pip install -e ".[dev]"

# 运行开发服务器
uvicorn main:app --reload

# 数据库迁移
alembic upgrade head
alembic revision --autogenerate -m "描述"

# 代码质量
black .              # 格式化
ruff check .         # 代码检查
mypy .               # 类型检查
pre-commit run --all # 预提交钩子
```

### 前端开发
```bash
cd frontend-demo

# 安装依赖
npm install

# 本地开发
npm run dev

# 构建生产版本
npm run build

# 代码检查
npm run lint
npm run typecheck
```

### Docker 操作
```bash
# 启动所有服务
docker-compose up -d

# 仅启动前端
docker-compose up -d frontend-demo

# 仅启动后端
docker-compose up -d api celery-worker celery-beat

# 查看日志
docker-compose logs -f frontend-demo
docker-compose logs -f api

# 重启服务
docker-compose restart frontend-demo

# 停止服务
docker-compose down
```

---

## ⚙️ 配置管理

### 环境变量
所有配置通过 `.env` 文件管理（从 `.env.example` 复制）：

```bash
# 后端配置
cp backend/.env.example backend/.env
# 编辑 backend/.env 填写实际值

# 前端配置
cp frontend-demo/.env.example frontend-demo/.env
# 编辑 frontend-demo/.env 填写 Supabase 配置
```

### 关键配置项
- **音频处理**: 片段时长 2-8 秒，采样率 16kHz 单声道
- **语义搜索**: 向量维度 1024，相似度阈值 0.25
- **AI 集成**: 阿里云 API 密钥、DashVector 端点
- **安全**: JWT 密钥、CORS 配置

---

## 🎯 项目规划与目标

### 2.0 DEMO 版本（当前阶段）
**目标**: 创建核心功能精简的演示版本，专注于快速部署和核心用户体验

**核心功能**:
- ✅ 默认登录（免认证，模拟用户）
- ✅ 音频上传与智能裁切
- ✅ 语弹库管理
- ✅ AI对话实验室
- ✅ 一键部署与阿里云 SLB 适配

**技术调整**:
- 前端移除 Supabase 依赖，直接集成 FastAPI 后端
- 后端简化认证流程，支持模拟用户
- 数据库模型精简，保留核心表结构
- 部署优化：一键部署脚本，阿里云 SLB 直接代理

**成功标准**:
1. 前端可在无认证情况下直接使用
2. 音频上传、裁切、管理功能正常
3. AI对话实验室可进行语义交互
4. 一键部署脚本可成功部署到阿里云
5. 通过阿里云 SLB 可正常访问服务

### 长期规划
1. **微信认证重新集成**（可选扩展）
2. **高级音频处理功能**（多轨道混音、效果器）
3. **多用户协作功能**（团队语弹库、共享项目）
4. **移动端适配优化**（微信小程序、React Native）

---

## 📈 开发状态

### 已完成
- ✅ 项目结构搭建
- ✅ 后端 FastAPI 框架 (50+ Python 文件)
- ✅ 前端 React + TypeScript (15+ 文件)
- ✅ 6 个数据库表定义
- ✅ 音频处理服务 (ASR、静音分割)
- ✅ 语义搜索服务 (DashVector)
- ✅ AI 模型集成 (ASR/TTS/NLP/LLM)
- ✅ Docker 容器化部署
- ✅ 依赖安装完成 (Python 154 个, npm 288 个)

### 待开发（2.0 DEMO 版优先）
- ⏳ 前端 Supabase 移除与 FastAPI 集成
- ⏳ 后端认证简化与模拟用户支持
- ⏳ 一键部署脚本与阿里云 SLB 适配
- ⏳ 预设提示词（点赞保存）后端逻辑

### 长期待开发
- ⏳ 微信小程序前端
- ⏳ 完整的音频生成流程
- ⏳ 微信认证系统
- ⏳ 个性化推荐
- ⏳ 性能优化和监控

---

## 📝 文档索引

- [CLAUDE.md](CLAUDE.md) - Claude Code 操作守则与开发命令
- [backend/README.md](backend/README.md) - 后端详细文档
- [docker-compose.yml](docker-compose.yml) - Docker 配置说明
- [docs/tasks/2.0DEMO版/2.0DEMO版最终执行方案.md](docs/tasks/2.0DEMO版/2.0DEMO版最终执行方案.md) - 2.0 DEMO 版详细实施计划

---

## 🔒 安全与隐私

- ✅ 所有密钥通过环境变量管理
- ✅ `.gitignore` 配置，敏感文件不会被提交
- ✅ JWT 认证 (HS256 算法)
- ✅ Row Level Security (Supabase 前端)
- ✅ API 端点速率限制

---

## 🤝 贡献指南

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 📄 许可证

MIT License

---

## 📞 联系我们

- 问题反馈: 请提交 [Issue](https://github.com/<username>/SoundVerse/issues)
- 功能建议: 请提交 [Pull Request](https://github.com/<username>/SoundVerse/pulls)

---

**项目状态**: ✅ **健康，可立即开发**  
**最后更新**: 2026-04-05
