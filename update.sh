#!/bin/bash

# SoundVerse 快速更新脚本
# 仅更新代码，不重建镜像

set -e

SERVER_IP=${1:-"your-server-ip"}
APP_NAME="soundverse-demo"

# 配置文件路径
CONFIG_FILE="deploy-config.json"

# 默认配置
SSH_USER="root"
SSH_PORT=22

# 如果存在配置文件，读取配置
if [ -f "$CONFIG_FILE" ]; then
    # 检查是否安装了jq
    if command -v jq &> /dev/null; then
        echo "读取配置文件: $CONFIG_FILE"
        # 使用jq解析JSON配置
        SERVER_IP=$(jq -r '.server_ip // empty' "$CONFIG_FILE" || echo "$SERVER_IP")
        APP_NAME=$(jq -r '.app_name // empty' "$CONFIG_FILE" || echo "$APP_NAME")
        SSH_USER=$(jq -r '.ssh_user // "root"' "$CONFIG_FILE")
        SSH_PORT=$(jq -r '.ssh_port // 22' "$CONFIG_FILE")
    else
        echo "未找到jq命令，跳过配置文件读取，使用默认参数"
    fi
fi

# 如果命令行提供了服务器IP，则覆盖配置文件中的设置
if [ -n "$1" ] && [ "$1" != "your-server-ip" ]; then
    SERVER_IP="$1"
fi

if [ -z "$SERVER_IP" ] || [ "$SERVER_IP" = "your-server-ip" ]; then
    echo "请指定服务器IP地址: ./update.sh 1.2.3.4"
    exit 1
fi

echo "开始快速更新..."

# 同步代码
rsync -avz --progress -e "ssh -p ${SSH_PORT}" \
    --exclude='.git' \
    --exclude='node_modules' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.env' \
    --exclude='.DS_Store' \
    ./ ${SSH_USER}@$SERVER_IP:/opt/${APP_NAME}/

# 重启前端服务（热重载）
ssh ${SSH_USER}@$SERVER_IP -p ${SSH_PORT} "cd /opt/${APP_NAME} && docker-compose restart frontend-demo"

echo "快速更新完成！前端已重启。"