# 项目测试管理制度

## 1. 制度目标

规范测试文档和测试数据的管理，确保测试资产整洁、可复用、易维护。

## 2. 文件夹结构

```
test/
├── README.md                    # 测试中心索引
├── TEST_MANAGEMENT.md           # 本文档 - 测试管理制度
├── data/                        # 测试数据
│   ├── fixtures/                # 固定测试数据
│   ├── generated/               # 生成式测试数据
│   └── archive/                 # 历史测试数据
├── reports/                     # 测试报告
│   └── archive/                 # 历史报告
└── temp/                        # 临时测试文件
    └── README.md
```

## 3. 测试数据分类

### 3.1 固定数据 (data/fixtures/)
- **用途**: 可复用的基准测试数据
- **示例**: 标准音频文件、参考JSON、基准配置
- **命名**: `{功能}_{描述}.{扩展名}`
- **保留期**: 永久保留

### 3.2 生成数据 (data/generated/)
- **用途**: 测试过程中生成的数据
- **示例**: 批量导入结果、完整性审计结果
- **命名**: `{类型}_{日期}_{时间}.{扩展名}`
- **清理**: 每月清理，重要数据移至 fixtures/

### 3.3 历史数据 (data/archive/)
- **用途**: 归档的旧测试数据
- **移动**: 超过3个月的生成数据自动归档
- **保留期**: 6个月，之后可删除

## 4. 测试报告管理

### 4.1 报告存放 (reports/)
- **当前报告**: 直接存放于 reports/
- **历史报告**: 超过1个月的报告移至 archive/
- **命名**: `{类型}_report_{日期}.md`

### 4.2 报告类型
| 类型 | 说明 | 示例 |
|------|------|------|
| ingestion | 入库测试报告 | ingestion_results_*.json |
| audit | 审计报告 | integrity_audit_*.json |
| encoding | 编码测试报告 | audio_transcription_encoding_report.md |

## 5. 临时文件管理

### 5.1 temp/ 目录用途
- 存放一次性测试文件
- 临时调试输出
- 未分类的测试数据

### 5.2 自动清理规则
```bash
# 每天自动清理超过7天的临时文件
find test/temp/ -type f -mtime +7 -delete
```

### 5.3 禁止存放
- ❌ 不能存放超过1天的文件
- ❌ 不能存放重要测试数据
- ❌ 不能存放生产环境数据

## 6. 数据迁移流程

### 从 backend/storage/ 迁移
1. `ingestion_results_*.json` → `test/data/fixtures/`
2. `integrity_audit_*.json` → `test/data/fixtures/`
3. 测试报告 → `test/reports/`

## 7. 命名规范

### 测试数据
```
{类型}_{日期}_{时间}_{描述}.{扩展名}

例如: ingestion_results_20260315_012415.json
- 类型: ingestion_results
- 日期: 2026-03-15
- 时间: 01:24:15
```

### 测试报告
```
{类型}_report_{日期}.md

例如: audio_transcription_encoding_report_20260322.md
```

## 8. 清理计划

| 目录 | 清理周期 | 保留策略 |
|------|----------|----------|
| test/temp/ | 每天 | 保留7天 |
| test/data/generated/ | 每月 | 保留1个月 |
| test/reports/archive/ | 每季度 | 保留6个月 |
| test/data/archive/ | 每季度 | 保留6个月 |
