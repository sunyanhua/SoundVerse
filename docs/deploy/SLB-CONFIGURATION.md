# SoundVerse 阿里云SLB配置指南

本文档提供 SoundVerse 2.0 DEMO 版本适配阿里云SLB（Server Load Balancer）的详细配置指南。

## 概述

SoundVerse 2.0 DEMO 版本已经优化架构，去除了Nginx反向代理，由SLB直接代理前端和后端服务。这种架构简化了部署，提高了可维护性。

### 架构变化
- **旧架构**: 客户端 → SLB → Nginx → (前端/API)
- **新架构**: 客户端 → SLB → (前端/API直接)

### 服务端口映射
| 服务 | 容器内部端口 | 主机暴露端口 | SLB监听端口 | 协议 |
|------|-------------|------------|------------|------|
| 前端DEMO | 5173 | 5173 | 80 (HTTP) | HTTP |
| 后端API | 8000 | 8000 | 8000 (HTTP) | HTTP |

## 1. 监听配置

### 1.1 基本监听配置表
在阿里云SLB控制台配置以下监听规则：

| 协议 | 前端端口 (SLB) | 后端端口 (ECS) | 健康检查路径 | 说明 |
|------|---------------|---------------|------------|------|
| HTTP | 80 | 5173 | `/` | 前端访问端口，HTTP流量 |
| HTTP | 443 | 5173 | `/` | 前端访问端口，HTTPS流量 (可选) |
| HTTP | 8000 | 8000 | `/api/health` | 后端API服务端口 |

### 1.2 详细监听配置

#### 前端服务监听 (端口 80/443)
- **监听端口**: 80 (HTTP) 或 443 (HTTPS)
- **后端端口**: 5173
- **调度算法**: 加权轮询 (wrr)
- **会话保持**: 关闭 (前端为无状态应用)
- **连接超时**: 60秒
- **空闲超时**: 15秒

#### 后端API服务监听 (端口 8000)
- **监听端口**: 8000
- **后端端口**: 8000
- **调度算法**: 加权轮询 (wrr)
- **会话保持**: 关闭 (API为无状态)
- **连接超时**: 60秒
- **空闲超时**: 15秒

## 2. 健康检查配置

### 2.1 前端健康检查配置
```
协议: HTTP
端口: 5173
路径: /
检查间隔: 5秒
超时时间: 2秒
健康阈值: 3 (连续成功3次标记为健康)
不健康阈值: 3 (连续失败3次标记为不健康)
正常状态码: http_2xx,http_3xx
```

### 2.2 后端API健康检查配置
```
协议: HTTP
端口: 8000
路径: /api/health
检查间隔: 5秒
超时时间: 2秒
健康阈值: 3
不健康阈值: 3
正常状态码: http_2xx
```

### 2.3 健康检查端点说明
SoundVerse 后端提供两个健康检查端点：
- `/api/health` - 专为SLB配置的健康检查端点
- `/health` - 通用的健康检查端点

两个端点返回相同的内容：
```json
{
  "status": "healthy",
  "timestamp": "2026-04-06T08:30:00Z",
  "services": {
    "database": "healthy",
    "redis": "healthy", 
    "dashvector": "healthy"
  }
}
```

## 3. 阿里云控制台配置步骤

### 3.1 准备工作
1. 确保已有阿里云账号并完成实名认证
2. 已创建SLB实例（传统型负载均衡CLB或应用型负载均衡ALB）
3. 已创建ECS实例并部署SoundVerse服务
4. 确保ECS安全组开放了5173和8000端口

### 3.2 配置前端服务监听 (端口80)
1. 登录 [阿里云SLB控制台](https://slb.console.aliyun.com)
2. 选择目标SLB实例，点击"监听配置"
3. 点击"添加监听"，选择"HTTP/HTTPS"
4. 配置监听参数：
   - 监听端口：80
   - 后端端口：5173
   - 调度算法：加权轮询 (wrr)
5. 配置健康检查：
   - 协议：HTTP
   - 端口：5173
   - 路径：/
   - 间隔：5秒，超时：2秒
   - 健康阈值：3，不健康阈值：3
6. 点击"下一步"，添加后端服务器（选择部署SoundVerse的ECS实例）
7. 权重设置为100，端口5173
8. 点击"提交"，完成配置

### 3.3 配置后端API监听 (端口8000)
1. 在同一个SLB实例中，再次点击"添加监听"
2. 选择"HTTP/HTTPS"
3. 配置监听参数：
   - 监听端口：8000
   - 后端端口：8000
   - 调度算法：加权轮询 (wrr)
4. 配置健康检查：
   - 协议：HTTP
   - 端口：8000
   - 路径：/api/health
   - 间隔：5秒，超时：2秒
   - 健康阈值：3，不健康阈值：3
5. 添加相同的后端服务器，端口8000
6. 点击"提交"，完成配置

### 3.4 验证配置
1. 等待2-3分钟让健康检查生效
2. 在SLB控制台查看后端服务器状态，应为"运行中"
3. 通过SLB地址访问服务：
   - 前端：`http://slb-ip/`
   - 后端健康检查：`http://slb-ip:8000/api/health`

## 4. 阿里云CLI自动化配置

### 4.1 安装和配置CLI
```bash
# 安装阿里云CLI
pip install aliyun-cli

# 配置访问密钥
aliyun configure set \
  --profile default \
  --mode AK \
  --region cn-hangzhou \
  --access-key-id YOUR_ACCESS_KEY_ID \
  --access-key-secret YOUR_ACCESS_KEY_SECRET
```

### 4.2 自动化配置脚本
创建 `slb-config.sh` 脚本：

```bash
#!/bin/bash

# SoundVerse SLB自动化配置脚本
# 需要安装aliyun-cli并配置AK/SK

set -e

# 配置变量（根据实际情况修改）
SLB_ID="lb-xxx"                    # SLB实例ID
SERVER_ID="i-xxx"                  # ECS实例ID
SERVER_IP="1.2.3.4"                # ECS实例私网IP
REGION="cn-hangzhou"               # 区域

echo "开始配置SoundVerse SLB..."

# 1. 创建前端HTTP监听 (端口80 -> 5173)
echo "配置前端HTTP监听 (80 -> 5173)..."
aliyun slb CreateLoadBalancerTCPListener \
  --LoadBalancerId $SLB_ID \
  --ListenerPort 80 \
  --BackendServerPort 5173 \
  --Bandwidth -1 \
  --Scheduler wrr \
  --PersistenceTimeout 0 \
  --HealthCheckType tcp \
  --HealthCheckDomain "$SERVER_IP" \
  --HealthCheckURI "/" \
  --HealthyThreshold 3 \
  --UnhealthyThreshold 3 \
  --HealthCheckTimeout 5 \
  --HealthCheckInterval 2 \
  --HealthCheckHttpCode "http_2xx,http_3xx" \
  --RegionId $REGION

# 2. 创建API监听 (端口8000 -> 8000)
echo "配置API监听 (8000 -> 8000)..."
aliyun slb CreateLoadBalancerTCPListener \
  --LoadBalancerId $SLB_ID \
  --ListenerPort 8000 \
  --BackendServerPort 8000 \
  --Bandwidth -1 \
  --Scheduler wrr \
  --PersistenceTimeout 0 \
  --HealthCheckType tcp \
  --HealthCheckDomain "$SERVER_IP" \
  --HealthCheckURI "/api/health" \
  --HealthyThreshold 3 \
  --UnhealthyThreshold 3 \
  --HealthCheckTimeout 5 \
  --HealthCheckInterval 2 \
  --HealthCheckHttpCode "http_2xx" \
  --RegionId $REGION

# 3. 添加后端服务器
echo "添加后端服务器..."
aliyun slb AddBackendServers \
  --LoadBalancerId $SLB_ID \
  --BackendServers "[{\"ServerId\":\"$SERVER_ID\",\"Weight\":\"100\",\"Type\":\"ecs\"}]" \
  --RegionId $REGION

echo "SLB配置完成！"
echo ""
echo "配置摘要："
echo "- 前端HTTP监听: 80端口 → ECS:5173端口"
echo "- API监听: 8000端口 → ECS:8000端口"
echo "- 健康检查: 前端(/) 和 API(/api/health)"
echo ""
echo "验证命令："
echo "  前端访问: curl http://SLB公网IP/"
echo "  API健康检查: curl http://SLB公网IP:8000/api/health"
```

### 4.3 脚本使用说明
1. 修改脚本中的配置变量：
   - `SLB_ID`: SLB实例ID（可在控制台查看）
   - `SERVER_ID`: ECS实例ID
   - `SERVER_IP`: ECS实例私网IP
   - `REGION`: 区域ID

2. 赋予执行权限并运行：
   ```bash
   chmod +x slb-config.sh
   ./slb-config.sh
   ```

3. 验证配置：
   ```bash
   # 查看监听配置
   aliyun slb DescribeLoadBalancerListeners --LoadBalancerId $SLB_ID
   
   # 查看后端服务器
   aliyun slb DescribeHealthStatus --LoadBalancerId $SLB_ID --ListenerPort 80
   ```

## 5. 防火墙和安全组配置

### 5.1 ECS安全组配置
在ECS安全组中开放以下端口：

| 端口 | 协议 | 源IP | 说明 |
|------|------|------|------|
| 22 | TCP | 0.0.0.0/0 | SSH管理 (建议限制为管理IP) |
| 80 | TCP | 0.0.0.0/0 | HTTP前端访问 |
| 443 | TCP | 0.0.0.0/0 | HTTPS前端访问 (可选) |
| 8000 | TCP | 0.0.0.0/0 | API服务访问 |
| 5173 | TCP | SLB私网IP段 | 前端服务 (仅SLB访问) |
| 3306 | TCP | 内网IP段 | MySQL数据库 (仅内网) |
| 6379 | TCP | 内网IP段 | Redis缓存 (仅内网) |

### 5.2 SLB安全组配置
SLB安全组需要允许：
- 入方向：0.0.0.0/0 访问 80, 443, 8000端口
- 出方向：到ECS私网IP的5173, 8000端口

### 5.3 系统防火墙配置 (Ubuntu)
```bash
# 开放必要端口
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 8000/tcp
sudo ufw allow 5173/tcp

# 启用防火墙
sudo ufw enable
sudo ufw status
```

## 6. 测试与验证

### 6.1 基础连通性测试
```bash
# 测试前端访问
curl -v http://SLB公网IP/

# 测试API健康检查
curl -v http://SLB公网IP:8000/api/health

# 测试API文档
curl -v http://SLB公网IP:8000/docs
```

### 6.2 功能完整性测试
1. **前端功能测试**
   - 访问前端界面，验证页面加载正常
   - 测试音频上传功能
   - 测试AI对话实验室
   - 测试语弹库浏览

2. **API功能测试**
   ```bash
   # 测试音频列表API
   curl http://SLB公网IP:8000/api/v1/audio/segments
   
   # 测试预设提示词API
   curl http://SLB公网IP:8000/api/v1/prompts/random
   ```

3. **健康检查模拟测试**
   ```bash
   # 模拟健康检查失败
   # 停止后端服务，观察SLB健康检查状态变化
   ssh ecs-user@ecs-ip "cd /opt/soundverse-demo && docker-compose stop api"
   
   # 等待1分钟后检查SLB控制台，后端服务器状态应变为"异常"
   
   # 恢复服务
   ssh ecs-user@ecs-ip "cd /opt/soundverse-demo && docker-compose start api"
   
   # 等待1分钟后检查状态应恢复为"运行中"
   ```

### 6.3 性能测试
```bash
# 使用ab进行简单压力测试
ab -n 1000 -c 10 http://SLB公网IP:8000/api/health

# 测试前端页面性能
ab -n 500 -c 5 http://SLB公网IP/
```

## 7. 监控与告警

### 7.1 SLB监控指标
在阿里云控制台监控以下关键指标：
- **QPS** (每秒查询数): 监控API请求频率
- **响应时间**: API平均响应时间，应 < 500ms
- **错误率**: HTTP 5xx错误比例，应 < 0.1%
- **带宽使用**: 进出流量监控
- **活跃连接数**: 并发连接监控

### 7.2 配置告警规则
建议配置以下告警：
1. **健康检查失败告警**
   - 规则: 后端服务器健康检查失败 > 1台
   - 级别: 紧急
   - 动作: 短信/邮件通知

2. **高错误率告警**
   - 规则: HTTP 5xx错误率 > 1%
   - 级别: 警告
   - 动作: 邮件通知

3. **高延迟告警**
   - 规则: 平均响应时间 > 1000ms
   - 级别: 警告
   - 动作: 邮件通知

### 7.3 自定义监控脚本
```bash
#!/bin/bash
# slb-monitor.sh - SLB状态监控脚本

SLB_ID="lb-xxx"
ALARM_URL="https://oapi.dingtalk.com/robot/send?access_token=xxx"

# 检查健康状态
health_status=$(aliyun slb DescribeHealthStatus --LoadBalancerId $SLB_ID --ListenerPort 8000 | jq -r '.BackendServers.BackendServer[0].ServerHealthStatus')

if [ "$health_status" != "normal" ]; then
    # 发送告警
    curl -H "Content-Type: application/json" -X POST $ALARM_URL -d '{
        "msgtype": "text",
        "text": {
            "content": "🚨 SoundVerse SLB健康检查失败！状态: '$health_status'"
        }
    }'
fi
```

## 8. 常见问题与解决方案

### 8.1 健康检查失败
**问题**: SLB健康检查失败，后端服务器状态为"异常"

**可能原因及解决方案**：
1. **端口未开放**
   ```bash
   # 检查ECS防火墙
   sudo netstat -tuln | grep -E ':5173|:8000'
   
   # 检查安全组规则
   # 确保5173和8000端口对SLB私网IP开放
   ```

2. **服务未运行**
   ```bash
   # 检查Docker服务状态
   docker ps | grep -E 'frontend|api'
   
   # 重启服务
   cd /opt/soundverse-demo && docker-compose restart
   ```

3. **健康检查路径错误**
   ```bash
   # 验证健康检查端点
   curl http://localhost:8000/api/health
   curl http://localhost:5173/
   ```

### 8.2 访问超时
**问题**: 通过SLB访问服务超时

**解决方案**：
1. 检查SLB到ECS的网络连通性
2. 检查ECS负载是否过高
3. 检查安全组和网络ACL规则
4. 调整SLB连接超时时间（默认60秒）

### 8.3 会话保持问题
**问题**: 需要会话保持但未配置

**解决方案**：
1. 在SLB监听配置中启用会话保持
2. 设置合适的会话保持超时时间（如3600秒）
3. 对于API服务，通常不需要会话保持

### 8.4 证书配置 (HTTPS)
**问题**: 需要配置HTTPS访问

**解决方案**：
1. 在SLB监听端口443配置SSL证书
2. 证书可从阿里云SSL证书服务获取或上传自有证书
3. 配置HTTP重定向到HTTPS（可选）

## 9. 最佳实践

### 9.1 高可用部署
1. **多可用区部署**: 在不同可用区部署ECS实例
2. **多SLB实例**: 主备SLB实例提高可用性
3. **自动伸缩**: 配置弹性伸缩组应对流量波动

### 9.2 安全最佳实践
1. **最小权限原则**: 安全组只开放必要端口
2. **网络隔离**: 使用VPC私有网络
3. **DDoS防护**: 开启阿里云DDoS基础防护
4. **WAF防护**: 配置Web应用防火墙

### 9.3 性能优化
1. **连接复用**: 配置HTTP Keep-Alive
2. **压缩传输**: 启用Gzip压缩
3. **缓存策略**: 合理配置缓存头
4. **CDN加速**: 静态资源使用CDN

## 10. 附录

### 10.1 相关文档
- [阿里云SLB产品文档](https://help.aliyun.com/product/27537.html)
- [SoundVerse部署指南](DEPLOYMENT.md)
- [SoundVerse架构文档](docs/architecture.md)

### 10.2 配置参数参考
| 参数 | 推荐值 | 说明 |
|------|--------|------|
| 健康检查间隔 | 5秒 | 检查频率，影响故障发现时间 |
| 健康检查超时 | 2秒 | 单次检查超时时间 |
| 健康阈值 | 3次 | 标记为健康需要的连续成功次数 |
| 不健康阈值 | 3次 | 标记为不健康需要的连续失败次数 |
| 连接超时 | 60秒 | 客户端到SLB连接超时 |
| 空闲超时 | 15秒 | 连接空闲超时时间 |

### 10.3 联系支持
如遇SLB配置问题，请：
1. 检查阿里云SLB监控和日志
2. 参考本文档故障排除章节
3. 联系阿里云技术支持
4. 提交SoundVerse项目Issue

---

**文档版本**: 1.0 (2026-04-06)  
**适用版本**: SoundVerse 2.0 DEMO  
**维护者**: SoundVerse 开发团队  
**最近更新**: 2026-04-06