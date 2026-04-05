# 2.0 DEMO版 - 阶段2：前端集成

## 目标
完成前端与后端的无缝集成，替换Supabase依赖为FastAPI调用，实现点赞保存功能
1. 移除Supabase依赖，集成FastAPI后端
2. 实现点赞保存前端逻辑
3. 修改"换一批"为随机提示词功能
4. 配置环境变量和API代理

## 预计耗时：2天

## 详细任务清单

### 任务2.1：移除Supabase依赖并安装必要包
**文件**: `frontend-demo/package.json`
**描述**: 移除Supabase相关依赖，添加必要的HTTP客户端
**具体步骤**：
1. 移除`@supabase/supabase-js`依赖
2. 可选的添加HTTP客户端（如`axios`或使用原生fetch）
3. 更新package.json后运行`npm install`
4. 清理Supabase相关的TypeScript类型定义

**文件**: `frontend-demo/src/lib/supabase.ts`（删除或修改）
**描述**: 替换Supabase客户端为API客户端
**具体步骤**：
1. 创建`frontend-demo/src/lib/api.ts`文件
2. 实现基础的API客户端，包含：
   - 统一的请求处理
   - 错误处理
   - 认证头管理（暂为空）
3. 删除或重命名原supabase.ts文件

**状态**: ✅ **2026-04-05**: Supabase依赖已移除，axios已安装

### 任务2.2：配置环境变量和API代理
**文件**: `frontend-demo/.env` 和 `frontend-demo/.env.example`
**描述**: 配置API基地址和环境变量
**具体步骤**：
1. 创建`.env.example`文件，包含：
   ```
   VITE_API_BASE_URL=http://localhost:8000/api/v1
   VITE_APP_MODE=demo
   ```
2. 复制为`.env`文件
3. 确保`.gitignore`包含`.env`

**文件**: `frontend-demo/vite.config.ts`
**描述**: 配置开发服务器代理，解决CORS问题
**具体步骤**：
1. 添加proxy配置，将`/api`代理到后端服务器
2. 参考2.0DEMO版最终执行方案第702-721行
3. 确保开发时前端可通过相对路径访问API

**状态**: ✅ **2026-04-05**: 环境变量和Vite代理配置完成

### 任务2.3：修改认证组件为免认证模式
**状态**: ✅ **2026-04-05**: AuthContext.tsx 已重写为免认证模拟用户模式


**文件**: `frontend-demo/src/components/Auth.tsx`
**描述**: 修改认证组件，支持免登录直接使用
**具体步骤**：
1. 移除微信登录相关逻辑
2. 修改为自动使用模拟用户
3. 保持组件结构不变，只修改逻辑
4. 确保应用启动时自动"登录"模拟用户

**文件**: `frontend-demo/src/contexts/AuthContext.tsx`
**描述**: 更新认证上下文，支持模拟用户
**具体步骤**：
1. 修改useAuth hook，返回模拟用户信息
2. 移除Supabase认证监听
3. 保持原有的接口类型，确保其他组件兼容

### 任务2.4：更新音频工坊页面API调用
**状态**: ✅ **2026-04-05**: UploadStudio.tsx 已替换Supabase调用为FastAPI上传


**文件**: `frontend-demo/src/pages/UploadStudio.tsx`
**描述**: 替换Supabase存储调用为FastAPI音频上传
**具体步骤**：
1. 查找所有`supabase.storage`调用
2. 替换为`fetch`或API客户端调用：
   - 上传音频：`POST /api/v1/audio/upload`
   - 获取音频列表：`GET /api/v1/audio/clips`
   - 删除音频：`DELETE /api/v1/audio/clips/{id}`
3. 保持原有的状态管理和UI交互
4. 更新相关的TypeScript类型定义

### 任务2.5：更新语弹库页面API调用
**状态**: ✅ **2026-04-05**: Library.tsx 已替换Supabase查询为FastAPI调用


**文件**: `frontend-demo/src/pages/Library.tsx`
**描述**: 替换Supabase数据库调用为FastAPI查询
**具体步骤**：
1. 查找所有`supabase.from('audio_clips')`调用
2. 替换为相应的API端点调用
3. 保持筛选、搜索、分页功能
4. 更新数据结构和错误处理

### 任务2.6：实现AI实验室点赞保存功能
**状态**: ✅ **2026-04-05**: AILab.tsx 已实现点赞保存和随机提示词功能，替换Supabase


**文件**: `frontend-demo/src/pages/AILab.tsx`
**描述**: 实现点赞保存和随机提示词功能
**具体步骤**：
1. **添加点赞按钮处理函数**（参考执行方案第318-336行）
   - 调用`PUT /api/v1/chat/messages/{id}/like`端点
   - 处理成功/失败反馈
   - 点赞后触发"换一批"刷新

2. **修改"换一批"功能**（参考执行方案第340-351行）
   - 调用`GET /api/v1/chat/preset-prompts/random`端点
   - 显示随机提示词列表
   - 点击提示词填充到输入框

3. **更新消息发送逻辑**
   - 替换Supabase对话记录为FastAPI调用
   - 调用`POST /api/v1/chat/message`发送消息
   - 保持原有的消息流和界面反馈

### 任务2.7：更新其他组件和工具函数
**状态**: ✅ **2026-04-05**: 全局搜索确认无残余Supabase引用


**文件**: 全局搜索Supabase引用
**描述**: 查找并替换所有Supabase相关调用
**具体步骤**：
1. 使用grep搜索`supabase`关键词
2. 逐个文件检查和替换
3. 主要关注的文件：
   - `src/components/`下的各种组件
   - `src/lib/`下的工具函数
   - `src/hooks/`下的自定义hook

### 任务2.8：前端集成测试
**测试流程**: 手动测试核心功能流程
**具体步骤**：
1. **启动前后端服务**：前端`npm run dev`，后端`uvicorn main:app --reload`
2. **免登录测试**：直接访问`http://localhost:5173`，应无需登录
3. **音频上传测试**：上传音频文件，查看裁切和列表显示
4. **AI对话测试**：发送消息，接收AI回复
5. **点赞保存测试**：点击消息点赞按钮，验证保存成功
6. **换一批测试**：点击换一批，显示随机提示词
7. **语弹库测试**：浏览、搜索、删除音频片段

## 验收标准
- [ ] 前端应用启动无Supabase相关错误
- [ ] 免登录直接进入系统
- [ ] 音频上传、裁切功能正常工作
- [ ] AI对话实验室可发送和接收消息
- [ ] 点赞按钮点击后保存成功
- [ ] "换一批"显示随机提示词
- [ ] 所有页面数据加载正常
- [ ] 开发环境代理配置正确，无CORS错误

## 相关文件
- `frontend-demo/package.json` - 依赖管理
- `frontend-demo/vite.config.ts` - 构建配置
- `frontend-demo/src/lib/api.ts` - API客户端
- `frontend-demo/src/pages/` - 核心页面
- `frontend-demo/src/components/Auth.tsx` - 认证组件
- `frontend-demo/src/contexts/` - 上下文提供者

## 依赖关系
- **前置依赖**：阶段1完成后端API改造
- **并行任务**：无

## 风险与缓解
1. **API兼容性问题**：保持前端请求格式与后端一致，充分测试
2. **状态管理混乱**：逐步替换，保持原有状态逻辑不变
3. **CORS问题**：配置开发服务器代理，避免跨域问题

## 完成标志
- 前端完全移除Supabase依赖
- 所有核心功能通过测试
- 创建PR并合并到开发分支
- 更新PROGRESS.md中的状态