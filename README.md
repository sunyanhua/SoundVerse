# SoundVerse - 听听·原声态

AI驱动的"声音百科+社交语库"微信小程序项目

## 项目概述

"听听·原声态"是一个基于AI驱动的"声音百科+社交语库"微信小程序。项目通过AI技术对广播节目进行颗粒度重构，建立声音库，实现智能音频互动和生成。

## 核心功能

1. **音频处理与重构**
   - 上传整期广播节目
   - AI自动按句拆分音频
   - 标记每个句子的：时间、节目、期数、说话人、语义标签

2. **智能音频互动**
   - 用户聊天：任何问题都能用匹配语义的广播音频回复
   - 语义上下文匹配

3. **音频生成与分享**
   - 生成祝福、表白、道歉、整蛊等定制音频
   - 用户转发分享功能

## 技术架构

### 前端（微信小程序）
- **框架**: 原生小程序 + TypeScript
- **UI组件库**: Vant Weapp
- **状态管理**: 小程序原生机制
- **开发环境**: 微信开发者工具

### 后端（Python FastAPI）
- **Web框架**: FastAPI
- **数据库**: MySQL + SQLAlchemy
- **缓存**: Redis
- **任务队列**: Celery + Redis
- **向量检索**: FAISS
- **AI服务**: 阿里云智能语音交互 + 自然语言处理

### AI模型集成
- **语音识别 (ASR)**: 阿里云智能语音交互
- **语音合成 (TTS)**: 阿里云智能语音交互
- **语义理解 (NLP)**: 阿里云自然语言处理
- **向量检索**: FAISS本地向量库

## 项目结构

```
SoundVerse/
├── wechat-miniprogram/          # 微信小程序前端
│   ├── src/
│   │   ├── pages/              # 页面目录
│   │   ├── components/         # 公共组件
│   │   ├── services/           # 服务层
│   │   ├── stores/             # 状态管理
│   │   └── utils/              # 工具函数
│   ├── app.json                # 小程序配置
│   ├── app.ts                  # 小程序入口
│   └── package.json            # 依赖管理
│
├── backend/                    # Python后端服务
│   ├── api/v1/                 # API路由
│   ├── services/               # 业务服务层
│   ├── shared/                 # 共享代码
│   │   ├── database/          # 数据库连接
│   │   ├── models/            # 数据模型
│   │   ├── schemas/           # Pydantic模型
│   │   └── utils/             # 工具函数
│   ├── ai-models/             # AI模型服务
│   ├── infrastructure/        # 基础设施配置
│   ├── main.py                # 应用入口
│   ├── config.py              # 配置管理
│   ├── pyproject.toml         # Python项目配置
│   └── docker-compose.yml     # Docker编排
│
└── CLAUDE.md                  # Claude Code项目说明
```

## 快速开始

### 环境要求

- Docker 和 Docker Compose
- Python 3.11+
- MySQL 8.0+
- Redis 7.0+
- 微信开发者工具（小程序开发）

### 后端开发环境启动

1. **克隆项目**
   ```bash
   git clone <repository-url>
   cd SoundVerse/backend
   ```

2. **启动开发环境**
   ```bash
   chmod +x scripts/start_dev.sh
   ./scripts/start_dev.sh
   ```

3. **配置环境变量**
   ```bash
   cp .env.example .env
   # 编辑 .env 文件，配置阿里云 API 密钥等
   ```

4. **访问 API 文档**
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

### 微信小程序开发

1. **安装依赖**
   ```bash
   cd ../wechat-miniprogram
   npm install
   ```

2. **使用微信开发者工具**
   - 打开微信开发者工具
   - 导入 `wechat-miniprogram` 目录
   - 配置小程序 AppID

3. **开发调试**
   - 修改代码后实时预览
   - 使用开发者工具调试功能

## 核心模块说明

### 1. 音频处理流程
```
音频上传 → 格式转换 → 静音分割 → ASR识别 → 语义向量化 → 存储索引
```

### 2. 语义匹配引擎
```
用户查询 → 文本向量化 → FAISS相似度搜索 → 音频片段匹配 → 返回音频URL
```

### 3. 音频生成系统
```
模板选择 → 变量填充 → TTS合成 → 背景音乐混合 → 生成音频 → 分享链接
```

### 4. 聊天交互系统
```
用户输入 → 语义匹配 → 音频回复 → 对话历史 → 个性化推荐
```

## 开发路线图

### 第一阶段：MVP核心功能（4周）
- [x] 项目基础框架搭建
- [ ] 微信小程序基础页面
- [ ] 后端API基础服务
- [ ] 阿里云AI服务集成
- [ ] 音频处理基础功能
- [ ] 语义匹配引擎实现

### 第二阶段：功能完善（3周）
- [ ] 音频生成功能
- [ ] 用户上传支持
- [ ] 个性化推荐
- [ ] 性能优化

### 第三阶段：扩展优化（后续）
- [ ] 更多音频模板
- [ ] 社交功能
- [ ] 商业化功能
- [ ] 多平台扩展

## API文档

启动后端服务后访问：
- **API文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/health
- **监控指标**: http://localhost:8000/metrics

## 配置说明

### 阿里云服务配置
需要开通以下阿里云服务：
1. **智能语音交互** (ASR/TTS)
2. **自然语言处理** (NLP)
3. **对象存储 OSS**
4. **云数据库 RDS** (MySQL)
5. **云数据库 Redis**

### 微信小程序配置
1. 注册微信小程序账号
2. 获取 AppID 和 AppSecret
3. 配置服务器域名

## 成本控制策略

### 第一阶段（MVP上线期）
- **服务器**: 2台2核4G云服务器（抢占实例）
- **存储**: 阿里云OSS 100GB
- **数据库**: MySQL基础版
- **AI API**: 严格控制调用频率
- **总计**: < 2000元/月

### 成本优化措施
- API调用配额管理
- 多层缓存机制
- 音频压缩存储
- 用户等级制API额度分配

## 许可证

MIT License

## 开发团队

- **全栈开发**: 2人（前端微信小程序 + 后端Python，AI集成）
- **产品/设计**: 1人（兼职，负责产品设计和用户体验）

## 联系我们

- 项目仓库: <repository-url>
- 问题反馈: 请提交 Issue
- 功能建议: 请提交 Pull Request

---

**注意**: 本项目处于早期开发阶段，API和功能可能会有较大变化。