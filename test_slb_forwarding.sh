#!/bin/bash

# SoundVerse SLB转发功能测试脚本
# 用于测试任务4.6：测试SLB转发功能

set -e

echo "=== SoundVerse SLB转发功能测试 ==="
echo "开始时间: $(date)"
echo

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_fail() { echo -e "${RED}[FAIL]${NC} $1"; }
log_info() { echo -e "${NC}[INFO]${NC} $1"; }

# 检查Docker服务状态
echo "1. 检查Docker服务状态..."
services=("SoundVerse-mysql" "SoundVerse-redis" "SoundVerse-api" "SoundVerse-frontend-demo")
for service in "${services[@]}"; do
    if docker ps --format '{{.Names}}' | grep -q "^${service}$"; then
        log_pass "$service 容器正在运行"
    else
        log_warn "$service 容器未运行"
    fi
done

echo

# 测试健康检查端点
echo "2. 测试健康检查端点..."
if docker ps --format '{{.Names}}' | grep -q "^SoundVerse-api$"; then
    # 测试 /health 端点
    if curl -f -s http://localhost:8000/health > /dev/null 2>&1; then
        log_pass "API健康检查端点 /health 可访问"
        # 获取健康状态详情
        health_response=$(curl -s http://localhost:8000/health)
        echo "   健康状态详情:"
        echo "$health_response" | jq . 2>/dev/null || echo "$health_response"
    else
        log_fail "API健康检查端点 /health 不可访问"
    fi

    # 测试 /api/health 端点
    if curl -f -s http://localhost:8000/api/health > /dev/null 2>&1; then
        log_pass "API健康检查端点 /api/health 可访问"
    else
        log_fail "API健康检查端点 /api/health 不可访问"
    fi
else
    log_warn "API容器未运行，跳过健康检查测试"
fi

echo

# 测试端口转发配置
echo "3. 测试端口转发配置..."
echo "   检查Docker Compose端口映射配置:"

# 检查API端口映射
if grep -q '"8000:8000"' docker-compose.yml 2>/dev/null; then
    log_pass "API服务端口映射正确 (8000:8000)"
else
    log_fail "API服务端口映射配置不正确"
fi

# 检查前端端口映射
if grep -q '"5173:5173"' docker-compose.yml 2>/dev/null; then
    log_pass "前端服务端口映射正确 (5173:5173)"
else
    log_fail "前端服务端口映射配置不正确"
fi

echo

# 测试前端访问（如果运行）
echo "4. 测试前端服务访问..."
if docker ps --format '{{.Names}}' | grep -q "^SoundVerse-frontend-demo$"; then
    if curl -f -s http://localhost:5173 > /dev/null 2>&1; then
        log_pass "前端服务可访问 (http://localhost:5173)"
    else
        log_fail "前端服务不可访问"
    fi
else
    log_warn "前端容器未运行，跳过前端访问测试"
fi

echo

# 测试SLB配置指南存在
echo "5. 测试SLB配置文档和脚本..."
if [ -f "SLB-CONFIGURATION.md" ]; then
    log_pass "SLB配置指南文件存在"
else
    log_fail "SLB配置指南文件不存在"
fi

if [ -f "slb-config.sh" ]; then
    log_pass "SLB自动化配置脚本存在"
    # 检查脚本语法
    if bash -n slb-config.sh; then
        log_pass "SLB配置脚本语法正确"
    else
        log_fail "SLB配置脚本语法错误"
    fi
else
    log_fail "SLB自动化配置脚本不存在"
fi

echo

# 总结
echo "=== 测试总结 ==="
echo "结束时间: $(date)"
echo
echo "测试项目:"
echo "1. Docker服务状态检查 - 完成"
echo "2. 健康检查端点测试 - 完成"
echo "3. 端口转发配置检查 - 完成"
echo "4. 前端服务访问测试 - 完成"
echo "5. SLB配置文档检查 - 完成"
echo
echo "注意: 此测试为本地模拟测试，实际SLB转发功能需要在阿里云环境中验证。"
echo "建议在部署到生产环境后，进行完整的SLB转发测试。"
echo
echo "测试完成。"