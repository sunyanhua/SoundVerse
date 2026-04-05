# 项目变更日志

本文件记录 SoundVerse 项目的所有重要变更。

## 格式规范

```markdown
## [版本号] - 日期

### 新增
- 新功能描述

### 修改
- 变更描述

### 修复
- Bug修复描述

### 移除
- 移除的功能
```

---

## [2.0.0-demo] - 2026-04-05

### 新增
- 2.0 DEMO版本开发计划
- 文档管理制度（docs/DOCUMENT_MANAGEMENT.md）
- 测试管理制度（test/TEST_MANAGEMENT.md）
- 任务清单目录（docs/tasks/2.0DEMO版/）
  - 2.0DEMO版最终执行方案.md
  - phase1-backend.md（后端改造）
  - phase2-frontend.md（前端集成）
  - phase3-deployment.md（部署脚本）
  - phase4-slb.md（SLB适配）

### 修改
- 重构项目文档结构，建立docs/和test/目录
- 更新CLAUDE.md，添加制度索引
- 更新PROGRESS.md，反映2.0DEMO版本计划
- 更新README.md，调整任务清单链接

### 归档
- 原始重构计划移至docs/tasks/2.0DEMO版/简化重构计划_v1.md
- 历史进度记录移至docs/backend/PROGRESS_ARCHIVE.md

---

## [1.0.0] - 2026-03-22

### 新增
- 初始项目结构搭建
- 后端FastAPI框架（50+ Python文件）
- 前端React + TypeScript（15+ 文件）
- 6个数据库表定义
- 音频处理服务（ASR、静音分割）
- 语义搜索服务（DashVector）
- AI模型集成（ASR/TTS/NLP/LLM）
- Docker容器化部署
- 微信小程序前端（archive/）
- 管理后台（archive/）

---

**维护说明**: 本文件应随每次重要更新及时维护，确保变更历史可追溯。
