#!/bin/sh
set -e

# 如果 node_modules 不存在，安装依赖
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

# 启动开发服务器
exec npm run dev -- --host 0.0.0.0
