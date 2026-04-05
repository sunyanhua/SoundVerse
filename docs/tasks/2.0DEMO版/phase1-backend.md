# 2.0 DEMO版 - 阶段1：后端改造

## 目标
完成后端核心功能改造，为2.0 DEMO版提供基础支持，包括：
1. 点赞保存功能数据库模型和API
2. 默认认证模式（模拟用户）
3. API路径前缀优化

## 预计耗时：2天

## 详细任务清单

### 任务1.1：添加PresetPrompt模型和数据库迁移
**文件**: `backend/shared/models/chat.py`
**描述**: 在现有ChatMessage模型基础上添加PresetPrompt模型
**具体步骤**：
1. 打开`backend/shared/models/chat.py`文件
2. 在文件末尾添加PresetPrompt类定义（参考2.0DEMO版最终执行方案第58-96行）
3. 确保导入必要的模块（uuid, datetime, Column, String, Text, JSON, ForeignKey, relationship等）
4. 更新`__init__.py`文件确保模型可导入

**文件**: `backend/alembic/versions/20240405_add_preset_prompts.py`
**描述**: 创建数据库迁移脚本
**具体步骤**：
1. 在`backend/alembic/versions/`目录下创建迁移文件
2. 编写upgrade()函数创建preset_prompts表
3. 编写downgrade()函数删除表
4. 添加必要的索引（user_id, category, review_status, created_at）
5. 运行迁移测试：`alembic upgrade head`

**状态**: ✅ **2026-04-05**: 已完成

### 任务1.2：实现点赞保存API端点
**文件**: `backend/api/v1/chat.py`
**描述**: 添加点赞保存和预设提示词相关API
**具体步骤**：
1. 导入必要的模型和依赖（PresetPrompt, ChatMessage, User等）
2. 添加`create_preset_prompt`端点（POST `/preset-prompts`）
3. 添加`get_random_preset_prompts`端点（GET `/preset-prompts/random`）
4. 添加`like_message`端点（PUT `/messages/{message_id}/like`）
5. 实现逻辑：点赞消息 → 可选保存为预设提示词 → 返回成功响应
6. 添加适当的错误处理和日志记录

**状态**: ✅ **2026-04-05**: 已完成

### 任务1.3：修改默认认证为模拟用户
**文件**: `backend/api/v1/auth.py`
**描述**: 修改认证逻辑，支持免认证模拟用户
**具体步骤**：
1. 修改`get_current_user_or_mock`依赖函数
2. 在开发环境或无认证信息时返回模拟用户对象
3. 模拟用户ID固定（如"demo-user-001"）
4. 确保所有API端点可以正常使用模拟用户
5. 保留原有JWT认证逻辑，以备后续启用

**文件**: `backend/config.py`
**描述**: 添加环境变量控制认证模式
**具体步骤**：
1. 添加`AUTH_MODE`配置项（可选值：demo, jwt）
2. 默认设置为demo模式
3. 在认证服务中根据模式选择认证策略

**状态**: ✅ **2026-04-05**: 已完成

### 任务1.4：优化API路径前缀
**文件**: `backend/main.py`
**描述**: 配置API路径前缀，支持SLB健康检查
**具体步骤**：
1. 确保`app.include_router(api_router, prefix="/api/v1")`已配置
2. 添加健康检查端点兼容性：
   ```python
   @app.get("/api/health")
   @app.get("/health")
   async def health_check() -> Dict[str, Any]:
   ```
3. 验证两个端点都能正常响应

**状态**: ✅ **2026-04-05**: 已完成

### 任务1.5：后端功能测试
**测试脚本**: 创建测试文件验证核心功能
**具体步骤**：
1. 测试点赞保存API：`curl -X PUT http://localhost:8000/api/v1/chat/messages/msg-001/like`
2. 测试随机提示词API：`curl http://localhost:8000/api/v1/chat/preset-prompts/random?count=3`
3. 测试健康检查：`curl http://localhost:8000/api/health` 和 `curl http://localhost:8000/health`
4. 测试模拟用户认证：不带token访问受保护端点

**状态**: ✅ **2026-04-05**: 已完成

---

## 阶段1完成情况汇总

**完成日期**: 2026-04-05
**质检结果**: ✅ **通过**

### 第2轮质检验证

**质检时间**: 2026-04-05  
**质检结果**: ✅ **通过，第1轮问题全部修复**

| 检查项 | 第1轮状态 | 第2轮状态 | 验证方式 |
|--------|----------|----------|----------|
| Alembic配置文件 | ❌ 未提交 | ✅ 已修复 | `backend/alembic.ini` 已存在 |
| Alembic迁移脚本 | ❌ 未提交 | ✅ 已修复 | `backend/alembic/versions/` 已存在 |
| test.db忽略规则 | ❌ 未添加 | ✅ 已修复 | `.gitignore` 第273行已添加 |
| 模型__init__.py | ❌ 未提交 | ✅ 已修复 | 文件已提交 |

**Git提交记录**:
```
2793f0b Add alembic migration files for preset_prompts
3a7e8f9 Add test.db to gitignore
```

**结论**: 阶段1所有问题已修复，批准进入阶段2

### 已完成检查项

| 检查项 | 状态 | 文件位置 |
|--------|------|----------|
| PresetPrompt模型 | ✅ | `backend/shared/models/chat.py:182-219` |
| 数据库迁移脚本 | ✅ | `backend/alembic/versions/20240405_add_preset_prompts.py` |
| 点赞保存API | ✅ | `backend/api/v1/chat.py:676-755` |
| 随机提示词API | ✅ | `backend/api/v1/chat.py:613-673` |
| 创建预设提示词API | ✅ | `backend/api/v1/chat.py:544-610` |
| 模拟用户认证 | ✅ | `backend/api/v1/auth.py:34-77` |
| 聊天模拟用户依赖 | ✅ | `backend/api/v1/chat.py:52-189` |
| AUTH_MODE配置 | ✅ | `backend/config.py:29` |
| 健康检查端点 | ✅ | `backend/main.py:117-158` |
| API路由前缀 | ✅ | `backend/main.py:174` |

### 验证命令

```bash
# 1. 健康检查
curl http://localhost:8000/health
curl http://localhost:8000/api/health

# 2. 点赞API（需先登录或使用demo模式）
curl -X PUT http://localhost:8000/api/v1/chat/messages/{message_id}/like \
  -H "Content-Type: application/json" \
  -d '{"like": true, "save_as_preset": true}'

# 3. 随机提示词
curl "http://localhost:8000/api/v1/chat/preset-prompts/random?count=3"

# 4. 创建预设提示词
curl -X POST http://localhost:8000/api/v1/chat/preset-prompts \
  -H "Content-Type: application/json" \
  -d '{"query_text": "测试提示词", "category": "对话"}'
```

### 未提交文件清单
- `backend/alembic.ini` - Alembic配置文件
- `backend/alembic/` - 迁移脚本目录
- `backend/shared/models/__init__.py` - 模型初始化
- `backend/test.db` - 测试数据库（应加入.gitignore）

## 验收标准
- [ ] PresetPrompt模型在数据库中正确创建
- [ ] 数据库迁移脚本可成功执行和回滚
- [ ] 点赞保存API端点响应正常
- [ ] 随机提示词API返回正确格式数据
- [ ] 模拟用户认证在无token时正常工作
- [ ] 健康检查端点`/api/health`和`/health`都可访问
- [ ] 后端服务启动无错误

## 相关文件
- `backend/shared/models/chat.py` - 数据模型定义
- `backend/alembic/versions/20240405_add_preset_prompts.py` - 数据库迁移
- `backend/api/v1/chat.py` - 聊天相关API
- `backend/api/v1/auth.py` - 认证逻辑
- `backend/config.py` - 配置文件
- `backend/main.py` - 应用入口

## 依赖关系
- 无前置依赖，这是2.0 DEMO版的第一个阶段

## 风险与缓解
1. **数据库迁移失败**：在测试环境充分验证迁移脚本，保留备份
2. **API兼容性问题**：保持现有API不变，只添加新端点
3. **认证逻辑冲突**：通过环境变量控制认证模式，确保灵活切换

## 完成标志
- 所有任务完成并验证
- 创建PR并合并到开发分支
- 更新PROGRESS.md中的状态