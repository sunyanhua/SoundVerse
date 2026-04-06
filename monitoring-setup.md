# SoundVerse 性能优化和监控配置指南

本文档提供 SoundVerse 2.0 DEMO 版本在阿里云环境中的性能优化和监控配置指南。

## 概述

SoundVerse 采用多层监控体系，包括：
1. **基础设施监控**：阿里云SLB、ECS监控
2. **应用性能监控**：Prometheus + Grafana
3. **日志监控**：应用日志收集和分析
4. **业务监控**：关键业务指标监控

## 1. SLB监控配置

### 1.1 阿里云SLB监控指标

阿里云SLB提供丰富的监控指标，建议配置以下关键指标监控：

| 监控指标 | 说明 | 报警阈值建议 | 监控频率 |
|----------|------|--------------|----------|
| QPS (Query Per Second) | 每秒请求数 | > 1000 QPS | 1分钟 |
| 响应时间 | 平均响应时间 | > 500ms | 1分钟 |
| 错误率 | HTTP 5xx错误率 | > 1% | 1分钟 |
| 带宽使用 | 入流量/出流量 | > 80% 带宽 | 1分钟 |
| 活跃连接数 | 当前活跃连接数 | > 1000 | 1分钟 |
| 丢弃连接数 | 因超限丢弃的连接 | > 0 | 1分钟 |
| 健康检查状态 | 后端服务器健康状态 | 不健康 > 0 | 1分钟 |

### 1.2 阿里云监控控制台配置

1. **登录阿里云控制台** → **云监控**
2. **创建报警规则**：
   - 资源类型：负载均衡SLB
   - 实例选择：选择SoundVerse SLB实例
   - 设置报警规则（示例）：
     ```yaml
     规则名称: SLB-QPS-过高
     监控指标: QPS
     统计周期: 1分钟
     统计方法: 平均值
     阈值: > 1000
     连续周期: 3
     报警级别: 警告
     ```

3. **配置通知方式**：
   - 邮件通知
   - 短信通知
   - 钉钉机器人
   - 电话通知（紧急）

### 1.3 阿里云CLI监控命令

```bash
# 查看SLB监控数据
aliyun slb DescribeLoadBalancerMonitorData \
  --LoadBalancerId lb-xxx \
  --StartTime "2026-04-06T00:00:00Z" \
  --EndTime "2026-04-06T23:59:59Z" \
  --Period 60

# 设置SLB监控报警
aliyun cms PutResourceMetricRule \
  --RuleName "slb-qps-alert" \
  --Namespace acs_slb_dashboard \
  --MetricName qps \
  --Dimensions "[{\"instanceId\":\"lb-xxx\"}]" \
  --Period 60 \
  --Statistics Average \
  --Threshold 1000 \
  --ComparisonOperator GreaterThanThreshold \
  --EvaluationCount 3
```

## 2. 服务监控配置

### 2.1 Prometheus监控体系

SoundVerse已集成Prometheus监控，配置如下：

#### 2.1.1 Prometheus服务信息
- **服务名称**: SoundVerse-prometheus
- **访问地址**: http://localhost:9092 (外部) 或 http://prometheus:9090 (容器内)
- **数据保留**: 200小时
- **配置路径**: `backend/docker/prometheus/prometheus.yml`

#### 2.1.2 监控目标配置

```yaml
# backend/docker/prometheus/prometheus.yml 示例配置
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'soundverse-api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/metrics'
    
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']
      
  - job_name: 'mysql-exporter'
    static_configs:
      - targets: ['mysql-exporter:9104']
      
  - job_name: 'redis-exporter'
    static_configs:
      - targets: ['redis-exporter:9121']
```

### 2.2 关键监控指标

#### 2.2.1 应用性能指标
- **API响应时间**: `http_request_duration_seconds`
- **请求QPS**: `http_requests_total`
- **错误率**: `http_requests_total{status=~"5.."}`
- **活动连接数**: `http_connections_active`

#### 2.2.2 系统资源指标
- **CPU使用率**: `node_cpu_seconds_total`
- **内存使用**: `node_memory_MemAvailable_bytes`
- **磁盘空间**: `node_filesystem_avail_bytes`
- **网络流量**: `node_network_receive_bytes_total`

#### 2.2.3 数据库指标
- **MySQL连接数**: `mysql_global_status_threads_connected`
- **查询QPS**: `mysql_global_status_queries`
- **慢查询数**: `mysql_global_status_slow_queries`
- **InnoDB缓冲池命中率**: `mysql_innodb_buffer_pool_reads`

#### 2.2.4 Redis指标
- **内存使用**: `redis_memory_used_bytes`
- **连接数**: `redis_connected_clients`
- **命中率**: `redis_keyspace_hits_total / (redis_keyspace_hits_total + redis_keyspace_misses_total)`
- **命令执行数**: `redis_commands_processed_total`

### 2.3 Grafana仪表板（建议）

建议部署Grafana进行可视化监控：

```yaml
# docker-compose.yml 添加Grafana服务
grafana:
  image: grafana/grafana:latest
  container_name: SoundVerse-grafana
  ports:
    - "3000:3000"
  volumes:
    - grafana_data:/var/lib/grafana
    - ./backend/docker/grafana/dashboards:/etc/grafana/provisioning/dashboards
  environment:
    - GF_SECURITY_ADMIN_PASSWORD=admin123
  depends_on:
    - prometheus
  networks:
    - SoundVerse-network
```

#### 2.3.1 推荐仪表板
1. **应用概览仪表板**: API性能、错误率、响应时间
2. **系统资源仪表板**: CPU、内存、磁盘、网络
3. **数据库仪表板**: MySQL连接、查询性能、慢查询
4. **缓存仪表板**: Redis内存、命中率、连接数

## 3. 日志监控配置

### 3.1 应用日志结构

SoundVerse应用日志配置：
- **日志路径**: `backend/logs/soundverse.log`
- **日志级别**: INFO (生产环境)
- **日志格式**: JSON (便于解析)
- **日志轮转**: 按天轮转，保留30天

### 3.2 关键日志监控

#### 3.2.1 错误日志监控
- **HTTP 5xx错误**: 监控API错误响应
- **数据库连接错误**: 监控数据库连接异常
- **外部API调用失败**: 监控第三方服务调用失败
- **音频处理失败**: 监控音频处理异常

#### 3.2.2 性能日志监控
- **慢请求日志**: 响应时间 > 1秒的请求
- **大文件上传**: 文件大小 > 100MB的上传
- **高耗时任务**: 处理时间 > 10秒的任务

### 3.3 阿里云日志服务配置

建议使用阿里云日志服务进行日志收集和分析：

1. **创建Logstore**: `soundverse-logs`
2. **配置日志收集**:
   - 收集路径: `/app/logs/soundverse.log`
   - 日志格式: JSON
   - 采集间隔: 实时
3. **配置日志分析**:
   - 创建索引字段: level, method, path, status, duration
   - 设置查询分析
4. **配置监控告警**:
   - 错误率 > 1%
   - 慢请求 > 1秒
   - 关键服务异常

## 4. 性能优化配置

### 4.1 SLB性能优化

#### 4.1.1 连接池优化
```bash
# 调整SLB连接池配置
# 在阿里云控制台或通过CLI调整以下参数：

# 前端连接超时
ConnectionTimeout: 60  # 秒

# 后端连接超时
BackendConnectTimeout: 5  # 秒

# 空闲超时
IdleTimeout: 15  # 秒

# 最大连接数
MaxConnections: 5000
```

#### 4.1.2 健康检查优化
```yaml
# 健康检查配置建议
健康检查路径: /api/health
检查间隔: 2秒
超时时间: 5秒
健康阈值: 3次
不健康阈值: 3次
```

### 4.2 应用性能优化

#### 4.2.1 FastAPI性能优化
```python
# backend/config.py 性能优化配置
# 连接池配置
DATABASE_POOL_SIZE = 20
DATABASE_POOL_RECYCLE = 3600
DATABASE_MAX_OVERFLOW = 10

# Redis连接池
REDIS_POOL_SIZE = 10
REDIS_POOL_TIMEOUT = 30

# 请求超时配置
REQUEST_TIMEOUT = 30  # 秒
```

#### 4.2.2 缓存策略优化
```python
# 缓存配置优化
CACHE_TTL = 3600  # 全局缓存1小时
USER_CACHE_TTL = 1800  # 用户数据30分钟
AUDIO_CACHE_TTL = 86400  # 音频数据24小时
SEARCH_CACHE_TTL = 300  # 搜索结果5分钟
```

### 4.3 数据库性能优化

#### 4.3.1 MySQL性能优化
```sql
-- MySQL性能优化建议
-- 1. 索引优化
CREATE INDEX idx_audio_segments_created_at ON audio_segments(created_at);
CREATE INDEX idx_preset_prompts_is_active ON preset_prompts(is_active);

-- 2. 查询优化
-- 使用EXPLAIN分析慢查询
EXPLAIN SELECT * FROM audio_segments WHERE user_id = ?;

-- 3. 配置优化
-- 调整InnoDB缓冲池大小
SET GLOBAL innodb_buffer_pool_size = 1G;
```

#### 4.3.2 Redis性能优化
```bash
# Redis配置优化
# 内存管理
maxmemory 1gb
maxmemory-policy allkeys-lru

# 持久化配置
appendonly yes
appendfsync everysec

# 连接管理
maxclients 10000
timeout 300
```

## 5. 报警配置

### 5.1 报警级别定义

| 级别 | 响应时间 | 通知方式 | 响应要求 |
|------|----------|----------|----------|
| P0 (紧急) | 5分钟内 | 电话+短信+钉钉 | 立即处理 |
| P1 (严重) | 30分钟内 | 短信+钉钉 | 1小时内处理 |
| P2 (警告) | 2小时内 | 邮件+钉钉 | 当天处理 |
| P3 (提示) | 24小时内 | 邮件 | 3天内处理 |

### 5.2 关键报警规则

#### 5.2.1 SLB报警规则
```yaml
# P0级报警
- 规则名称: SLB-全部后端服务器不健康
- 触发条件: 健康后端服务器数 = 0
- 通知方式: 电话+短信+钉钉
- 响应要求: 立即处理

# P1级报警  
- 规则名称: SLB-QPS突增500%
- 触发条件: QPS环比增长 > 500%
- 通知方式: 短信+钉钉
- 响应要求: 1小时内处理
```

#### 5.2.2 应用报警规则
```yaml
# P1级报警
- 规则名称: API-错误率超阈值
- 触发条件: HTTP 5xx错误率 > 5%
- 通知方式: 短信+钉钉
- 响应要求: 1小时内处理

# P2级报警
- 规则名称: API-响应时间过慢
- 触发条件: 平均响应时间 > 2秒
- 通知方式: 邮件+钉钉
- 响应要求: 当天处理
```

#### 5.2.3 资源报警规则
```yaml
# P1级报警
- 规则名称: CPU-使用率过高
- 触发条件: CPU使用率 > 90% 持续5分钟
- 通知方式: 短信+钉钉
- 响应要求: 1小时内处理

# P2级报警
- 规则名称: 内存-使用率过高
- 触发条件: 内存使用率 > 85% 持续10分钟
- 通知方式: 邮件+钉钉
- 响应要求: 当天处理
```

## 6. 监控数据保留策略

### 6.1 监控数据保留周期

| 数据类型 | 原始数据保留 | 聚合数据保留 | 存储位置 |
|----------|--------------|--------------|----------|
| SLB监控指标 | 30天 | 1年 | 阿里云监控 |
| 应用性能指标 | 15天 | 180天 | Prometheus |
| 系统资源指标 | 15天 | 180天 | Prometheus |
| 日志数据 | 30天 | 1年 | 阿里云日志服务 |
| 业务指标 | 90天 | 2年 | 业务数据库 |

### 6.2 数据清理策略

```bash
# Prometheus数据清理配置
# 在prometheus.yml中配置
storage:
  tsdb:
    retention:
      time: 200h  # 保留200小时
      size: 50GB  # 最大50GB
      
# 阿里云日志服务配置
# 在Logstore中配置
数据存储时间: 30天
Shard自动分裂: 开启
热数据存储: 7天
```

## 7. 监控部署和验证

### 7.1 部署步骤

1. **基础监控部署**:
   ```bash
   # 启动Prometheus监控
   docker-compose up -d prometheus
   
   # 验证监控服务
   curl http://localhost:9092/targets
   curl http://localhost:9092/api/v1/query?query=up
   ```

2. **SLB监控配置**:
   - 在阿里云控制台配置SLB监控报警
   - 验证监控数据采集

3. **日志监控配置**:
   - 配置应用日志输出
   - 配置阿里云日志服务采集

### 7.2 监控验证检查清单

- [ ] SLB监控指标可正常采集
- [ ] Prometheus可正常采集应用指标
- [ ] 应用日志可正常输出和收集
- [ ] 报警规则配置正确
- [ ] 通知渠道配置正确
- [ ] 关键仪表板可正常展示

## 8. 附录

### 8.1 相关文档

- [SLB配置指南](SLB-CONFIGURATION.md) - 阿里云SLB详细配置
- [安全组配置指南](security-rules.md) - 防火墙和安全组配置
- [部署脚本](deploy.sh) - 自动化部署脚本

### 8.2 监控工具参考

- **阿里云监控**: https://monitor.aliyun.com
- **Prometheus**: https://prometheus.io
- **Grafana**: https://grafana.com
- **阿里云日志服务**: https://sls.console.aliyun.com

### 8.3 性能基准参考

| 指标 | 基准值 | 警告阈值 | 危险阈值 |
|------|--------|----------|----------|
| API响应时间 | < 200ms | > 500ms | > 2000ms |
| API错误率 | < 0.1% | > 1% | > 5% |
| CPU使用率 | < 60% | > 80% | > 90% |
| 内存使用率 | < 70% | > 85% | > 95% |
| MySQL连接数 | < 50 | > 100 | > 200 |
| Redis内存使用 | < 70% | > 85% | > 95% |

---

**更新日志**  
- 2026-04-06: 初始版本创建，包含SLB监控、应用监控、性能优化和报警配置