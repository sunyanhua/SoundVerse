#!/bin/bash

# SoundVerse 后端开发环境启动脚本

set -e

echo "🚀 启动 SoundVerse 开发环境..."

# 检查必要工具
command -v docker >/dev/null 2>&1 || { echo "❌ 需要安装 Docker"; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo "❌ 需要安装 Docker Compose"; exit 1; }

# 创建必要的目录
mkdir -p logs data

# 复制环境变量示例文件
if [ ! -f .env ]; then
    echo "📋 复制环境变量示例文件..."
    cp .env.example .env
    echo "⚠️  请编辑 .env 文件，配置必要的环境变量"
fi

# 启动 Docker 服务
echo "🐳 启动 Docker 服务..."
docker-compose up -d mysql redis

# 等待数据库就绪
echo "⏳ 等待数据库就绪..."
sleep 10

# 运行数据库迁移
echo "🗄️  初始化数据库..."
# 这里应该运行数据库迁移命令
# alembic upgrade head

# 启动后端 API 服务
echo "🌐 启动后端 API 服务..."
docker-compose up -d api

# 启动 Celery Worker
echo "⚙️  启动 Celery Worker..."
docker-compose up -d celery-worker

# 显示服务状态
echo "📊 服务状态:"
docker-compose ps

echo ""
echo "✅ 开发环境启动完成!"
echo ""
echo "📝 服务访问地址:"
echo "   - API 服务: http://localhost:8000"
echo "   - API 文档: http://localhost:8000/docs"
echo "   - 健康检查: http://localhost:8000/health"
echo ""
echo "🔧 管理命令:"
echo "   - 查看日志: docker-compose logs -f api"
echo "   - 停止服务: docker-compose down"
echo "   - 重建服务: docker-compose up -d --build"
echo ""
echo "💡 下一步:"
echo "   1. 编辑 .env 文件配置阿里云 API 密钥"
echo "   2. 访问 http://localhost:8000/docs 测试 API"
echo "   3. 开始开发!"