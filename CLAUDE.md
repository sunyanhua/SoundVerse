# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在本代码库中工作时提供操作守则和开发指导。

**核心原则**：
1. 优先使用已有代码结构和模式，避免不必要的重构
2. 保持UI原汁原味，禁止随意修改CSS/Tailwind/Framer Motion样式
3. API调用必须"无感"嵌入现有UI组件
4. 所有修改必须可回溯，重要变更需记录在docs/tasks/目录

**项目状态**：当前处于2.0 DEMO版开发阶段，专注于核心功能精简和部署优化。

## 项目开发任务执行机制
1. **管家派送任务流程**：
   - 管家根据 `PROGRESS.md` 中的工作计划，按阶段顺序调用CC执行具体任务
   - CC收到任务后，需首先读取对应阶段的任务清单文件（`docs/tasks/{版本号}/phase-*.md`），明确具体任务要求
   - 执行任务前，需确认任务在任务清单文件中的准确位置和描述

2. **任务执行和状态更新**：
   - 每完成一个任务，必须在对应的任务清单文件中标注“✅ 已完成”状态及完成时间戳
   - 任务状态更新格式：`- ✅ **2026-03-26**: 任务描述（实际完成时间）`
   - 大阶段完成后，需在 `PROGRESS.md` 中标注“✅ 已完成”状态及完成时间

3. **进度文档更新规范**：
   - `PROGRESS.md` 的更新仅限于以下情况：
     1. **状态概览更新**：项目状态、当前阶段、最新进展
     2. **各阶段完成状态更新**：阶段完成后标记完成状态
     3. **执行过程中出现的重大问题或调整**：需要记录的重大变更
   - **禁止**在 `PROGRESS.md` 中记录日常任务完成细节，这些细节应保留在任务清单文件中

4. **任务清单文件维护**：
   - 每个阶段的任务清单文件（`docs/tasks/{版本号}/phase-*.md`）是任务执行的唯一依据
   - 任务清单中的任务分解必须足够详细，确保管家安排实施时无误解
   - 任务完成后及时更新状态，保持清单与实际进度同步

- **单步执行原则**：在非交互式自动化（Butler）模式下，一个进程 = 一个原子任务。禁止在未重新启动进程的情况下自行处理后续任务，即便后续任务已在 TASK_REPORT.json 中标记为 WAITING。
- **强制退出机制**：完成指定 Step 后的第一动作是更新进度文档，第二动作是立即终止会话，严禁跨步执行。


## 🐳 Docker Development Protocol (Strict)
- **Identity**: Project uses `docker-compose.yml` with project name `soundverse`.
- **Hot-Reload**: 
  - Backend (API): Uses `uvicorn --reload`. Sources mapped to `/app`.
  - Frontend: Uses `npm run dev` with HMR. Sources mapped to `/app`.
  - **启用 Watch 模式**: 已配置 `develop.watch` 自动同步源码变更
- **Zero-Restart Policy** (严格执行):
  - **禁止**因源码改动而重启或重建容器
  - **禁止**运行 `docker-compose up --build` 或 `restart` 来应用代码变更
  - **信任热重载机制**: Uvicorn `--reload` 和 Vite HMR 会自动检测变更
  - **唯一重建条件**: 仅当 `requirements.txt`, `package.json`, 或 `Dockerfile` 变更时才重建
  - **修改后操作**: 保存文件后等待 1-2 秒，热重载会自动生效
- **Container Names**: Fixed as `soundverse-api`, `soundverse-frontend-demo`, etc.
- **故障排查**: 如热重载失效，检查日志而非重启容器


## 项目文档与测试管理制度

### 制度索引

| 制度 | 路径 | 说明 |
|------|------|------|
| 文档管理制度 | [docs/DOCUMENT_MANAGEMENT.md](docs/DOCUMENT_MANAGEMENT.md) | 文档创建、存储、归档规范 |
| 测试管理制度 | [test/TEST_MANAGEMENT.md](test/TEST_MANAGEMENT.md) | 测试数据、报告管理规范 |

### 文档中心 (docs/)

- [文档中心索引](docs/README.md) - 所有文档入口
- [任务清单](docs/tasks/) - 各版本任务清单
- [质检报告](docs/Audit_Report/) - 管家质检报告

### 测试中心 (test/)

- [测试中心索引](test/README.md) - 测试数据和报告入口
- [测试数据](test/data/) - 测试数据目录
- [测试报告](test/reports/) - 测试报告目录

**重要提示**: 所有文档和测试数据必须按制度存放，临时文件及时清理。

