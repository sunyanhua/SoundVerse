# 项目测试中心

本目录集中管理项目测试相关的数据和文档。

## 快速导航

| 类别 | 路径 | 说明 |
|------|------|------|
| 测试管理制度 | [TEST_MANAGEMENT.md](./TEST_MANAGEMENT.md) | 测试管理规范 |
| 测试数据 | [data/](./data/) | 测试数据目录 |
| 测试报告 | [reports/](./reports/) | 测试报告目录 |
| 测试脚本 | [scripts/](./scripts/) | 自动化测试脚本 |
| 临时文件 | [temp/](./temp/) | 临时测试文件 |

## 数据索引

### 固定测试数据 (data/fixtures/)
存放可复用的标准测试数据：
- **入库测试结果**: `ingestion_results_{日期}_{时间}.json` (10个文件)
- **完整性审计结果**: `integrity_audit_{日期}_{时间}.json` (4个文件)

### 生成测试数据 (data/generated/)
当前为空，测试过程中生成的数据将按月清理。

### 历史测试数据 (data/archive/)
存放归档的历史测试数据，保留6个月。

### 音频测试数据 (data/audio/)
存放音频测试文件（从根目录音频素材/迁移）：
- 《北京新闻》20250818期...
- 《大城小事》20250908期...
- 《欢乐正前方》20110718期...
- 《行走天下》20250908期...
- 《一路畅通》20250814期...
- 《娱乐72变》20250906期...
- 张会欣的双城生活...

共7个音频文件，用于音频上传和处理测试。

## 测试报告 (reports/)

当前报告：
- [audio_transcription_encoding_report.md](./reports/audio_transcription_encoding_report.md) - 音频转录编码测试报告

### 历史报告归档
超过1个月的报告移至 [reports/archive/](./reports/archive/)。

## 测试脚本 (scripts/)

自动化测试脚本：
- [test_deploy_functions.sh](./scripts/test_deploy_functions.sh) - 部署功能测试脚本
- [test_slb_forwarding.sh](./scripts/test_slb_forwarding.sh) - SLB转发功能测试脚本
- [test_upload.py](./scripts/test_upload.py) - 音频上传流程测试脚本

## 使用规范

1. **新增数据**: 根据类型放入对应目录
2. **临时文件**: 必须放入 temp/，7天后自动清理
3. **重要数据**: 及时从 generated/ 移至 fixtures/
4. **报告归档**: 超过1个月的报告移至 archive/
5. **测试脚本**: 所有测试脚本统一存放于 scripts/ 目录

## 清理状态

- **temp/**: 已清理，仅包含 README.md
- **data/generated/**: 已清理，当前为空
- **data/fixtures/**: 14个测试数据文件，符合命名规范
- **data/audio/**: 7个音频测试文件已归档
- **scripts/**: 3个测试脚本已归档
