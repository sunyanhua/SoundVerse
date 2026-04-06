#!/bin/bash

# 阿里云SLB自动配置脚本
# 需要安装aliyun-cli并配置AK/SK
# 使用方法: ./slb-config.sh <SLB_ID> <SERVER_ID> <SERVER_IP>

set -e

# 检查参数
if [ $# -lt 3 ]; then
    echo "使用方法: $0 <SLB_ID> <SERVER_ID> <SERVER_IP>"
    echo "示例: $0 lb-xxx i-xxx 1.2.3.4"
    exit 1
fi

SLB_ID="$1"
SERVER_ID="$2"
SERVER_IP="$3"

echo "配置阿里云SLB..."
echo "SLB实例ID: $SLB_ID"
echo "后端服务器ID: $SERVER_ID"
echo "后端服务器IP: $SERVER_IP"
echo ""

# 检查aliyun-cli是否安装
if ! command -v aliyun &> /dev/null; then
    echo "错误: aliyun-cli未安装"
    echo "请先安装: https://help.aliyun.com/document_detail/121541.html"
    exit 1
fi

# 1. 创建HTTP监听（前端80端口 -> 5173端口）
echo "1. 创建前端HTTP监听 (80端口 -> 5173端口)..."
aliyun slb CreateLoadBalancerHTTPListener \
  --LoadBalancerId "$SLB_ID" \
  --ListenerPort 80 \
  --BackendServerPort 5173 \
  --Bandwidth -1 \
  --Scheduler wrr \
  --StickySession off \
  --HealthCheckType tcp \
  --HealthCheckDomain "$SERVER_IP" \
  --HealthCheckURI "/" \
  --HealthyThreshold 3 \
  --UnhealthyThreshold 3 \
  --HealthCheckTimeout 5 \
  --HealthCheckInterval 2 \
  --HealthCheckConnectPort 5173

if [ $? -eq 0 ]; then
    echo "前端监听创建成功"
else
    echo "前端监听创建失败，可能已存在或参数错误"
fi

echo ""

# 2. 创建API监听（8000端口 -> 8000端口）
echo "2. 创建API HTTP监听 (8000端口 -> 8000端口)..."
aliyun slb CreateLoadBalancerHTTPListener \
  --LoadBalancerId "$SLB_ID" \
  --ListenerPort 8000 \
  --BackendServerPort 8000 \
  --Bandwidth -1 \
  --Scheduler wrr \
  --StickySession off \
  --HealthCheckType http \
  --HealthCheckDomain "$SERVER_IP" \
  --HealthCheckURI "/api/health" \
  --HealthyThreshold 3 \
  --UnhealthyThreshold 3 \
  --HealthCheckTimeout 5 \
  --HealthCheckInterval 2 \
  --HealthCheckConnectPort 8000

if [ $? -eq 0 ]; then
    echo "API监听创建成功"
else
    echo "API监听创建失败，可能已存在或参数错误"
fi

echo ""

# 3. 添加后端服务器
echo "3. 添加后端服务器..."
aliyun slb AddBackendServers \
  --LoadBalancerId "$SLB_ID" \
  --BackendServers "[{\"ServerId\":\"$SERVER_ID\",\"Weight\":\"100\"}]"

if [ $? -eq 0 ]; then
    echo "后端服务器添加成功"
else
    echo "后端服务器添加失败"
fi

echo ""
echo "SLB配置完成！"
echo ""
echo "重要提醒:"
echo "1. 确保安全组已开放80和8000端口"
echo "2. 确保后端服务器上的服务正在运行"
echo "3. 验证配置:"
echo "   前端访问: http://$SERVER_IP"
echo "   API健康检查: http://$SERVER_IP:8000/api/health"