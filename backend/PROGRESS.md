# SoundVerse 项目进度报告

## 当前状态 (2026-03-08)

### ✅ 已完成的修复

#### 1. ASR服务参数修正 (`backend/ai_models/asr_service.py`)
- **产品名称**: `nls-filetrans` (已测试`nls`和`nls-filetrans`)
- **动作名称**: `CreateFileTrans` (已测试`CreateFileTransJob`)
- **版本**: `2018-08-17` (已测试`2019-02-28` - 返回`InvalidVersion`)
- **端点**: `filetrans.cn-shanghai.aliyuncs.com`
- **区域**: `cn-shanghai` (ASR标准接入区)
- **OSS区域**: `cn-beijing` (保持不变)

#### 2. OSS存储服务简化 (`backend/services/storage_service.py`)
- **关键修复**: 移除所有自定义headers和metadata参数
- **签名问题**: 复杂路径上传出现`SignatureDoesNotMatch`错误
- **测试成功**: 简单路径`test/test_radio.mp3`上传成功
- **测试失败**: 复杂路径`audio/segments/...`上传失败

#### 3. 向量维度适配
- **config.py**: `VECTOR_DIMENSION`从1536改为1024 (text-embedding-v3标准)
- **DashVector**: 添加维度检查逻辑，不匹配时自动重新创建collection

#### 4. 新测试脚本
- `test_one_segment_full.py`: 单片段全流程验证脚本
- 问题：数据库模型依赖关系错误 (已修复ChatMessage导入)

### 🔴 当前阻塞问题

#### 1. ASR API 404错误
**症状**: `HTTP Status: 404 Error:InvalidAction.NotFound`
**已尝试参数组合**:
- 产品名称: `nls`, `nls-filetrans`
- 动作名: `CreateFileTrans`, `CreateFileTransJob`
- 版本: `2018-08-17`, `2019-02-28`
- 端点: `filetrans.cn-shanghai.aliyuncs.com`, `nls-filetrans.cn-shanghai.aliyuncs.com`

**可能原因**:
1. API动作名称不正确
2. API版本不匹配
3. 产品代码错误
4. 端点解析问题

#### 2. OSS签名不匹配
**症状**: `SignatureDoesNotMatch` (仅复杂路径)
**成功案例**: `https://ai-sun-vbegin-com-cn.oss-cn-beijing.aliyuncs.com/test/test_radio.mp3`
**失败案例**: 包含`audio/segments/...`的路径

**可能原因**:
1. 路径中的特殊字符
2. Content-Type自动推断差异
3. 文件大小或元数据影响

### ✅ 已验证正常工作

1. **数据库连接**: ✅ 容器内连接正常
2. **OSS基础上传**: ✅ 简单路径上传成功
3. **向量服务配置**: ✅ 维度适配完成
4. **NLP服务**: ✅ 使用text-embedding-v3
5. **DashVector**: ✅ 初始化和维度检查正常

### 📋 下一步行动计划

#### 优先级1: 解决ASR 404问题
1. **确认阿里云官方API参数**
   - 访问阿里云文档确认录音文件识别的准确参数
   - 检查AppKey有效性

2. **尝试API调试方法**
   ```python
   # 可能的调试方案
   # 1. 使用阿里云SDK的调试模式
   # 2. 直接使用HTTP请求测试
   # 3. 检查region_id和endpoint组合
   ```

3. **备用方案**: 暂时使用模拟模式继续其他流程测试

#### 优先级2: 修复OSS签名问题
1. **路径简化测试**
   - 使用更简单的路径格式
   - 避免特殊字符和过长路径

2. **上传方法对比**
   - 对比测试脚本和全流程脚本的差异
   - 检查文件大小和内容类型

#### 优先级3: 运行单片段验证
1. **修复数据库依赖后重新运行**
2. **目标**: 看到真实的ASR文本返回
3. **验证**: 搜索"北京时间"能成功召回片段

### 🔧 关键文件修改记录

#### `backend/ai_models/asr_service.py`
- 第179行: `RpcRequest('nls-filetrans', '2018-08-17', 'CreateFileTrans')`
- 第181行: `request.set_endpoint('filetrans.cn-shanghai.aliyuncs.com')`
- 第237行: `RpcRequest('nls-filetrans', '2018-08-17', 'GetFileTrans')`
- 第239行: `get_request.set_endpoint('filetrans.cn-shanghai.aliyuncs.com')`

#### `backend/services/storage_service.py`
- 第114行: `result = self.oss_bucket.put_object(object_key, f)` (移除headers)
- 第169行: `result = self.oss_bucket.put_object(object_key, audio_data)` (移除headers)

#### `backend/config.py`
- 第69行: `DASHSCOPE_EMBEDDING_MODEL: str = "text-embedding-v3"`
- 第76行: `DASHVECTOR_COLLECTION_DIMENSION: int = 1024`
- 第97行: `VECTOR_DIMENSION: int = 1024`

#### `backend/services/search_service.py`
- 第336-349行: 添加了DashVector collection维度检查逻辑

### 🚀 快速恢复指南

1. **重启开发环境**:
   ```bash
   cd backend
   docker-compose up -d
   ```

2. **运行单片段测试**:
   ```bash
   docker-compose exec api python scripts/test_one_segment_full.py
   ```

3. **测试ASR服务**:
   ```bash
   docker-compose exec api python -c "
   import asyncio, sys
   sys.path.insert(0, '/app')
   from ai_models.asr_service import init_asr_service, recognize_audio_file
   async def test():
       await init_asr_service()
       result = await recognize_audio_file('/app/test_radio.mp3', language='zh-CN', sample_rate=16000, format='mp3')
       print(f'Result: {result}')
   asyncio.run(test())
   "
   ```

### 📝 待验证假设

1. **阿里云API版本**: 可能需要`2019-02-28`但之前返回`InvalidVersion`
2. **产品代码**: 可能应该是`nls`而不是`nls-filetrans`
3. **端点格式**: 可能需要HTTPS端点或不同格式
4. **OSS路径**: 复杂路径中的`/`字符可能导致签名计算差异

### 🔍 建议的调试步骤

1. **查看阿里云控制台**确认ASR服务的API详情
2. **检查AppKey权限**是否包含录音文件识别服务
3. **使用curl测试**直接API调用
4. **联系阿里云支持**获取准确的API参数

---
**下次重启时优先处理ASR API参数确认和OSS路径简化测试**