#!/bin/bash

# SoundVerse 2.0 DEMO 一键部署脚本
# 使用方法: ./deploy.sh [环境: dev/prod] [服务器IP]

set -e  # 遇到错误立即退出

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 配置参数
ENV=${1:-"prod"}
SERVER_IP=${2:-"your-server-ip"}
APP_NAME="soundverse-demo"
BACKUP_DIR="./backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# 配置文件路径
CONFIG_FILE="deploy-config.json"

# 如果存在配置文件，读取配置
if [ -f "$CONFIG_FILE" ]; then
    # 检查是否安装了jq
    if command -v jq &> /dev/null; then
        log_info "读取配置文件: $CONFIG_FILE"
        # 使用jq解析JSON配置
        SERVER_IP=$(jq -r '.server_ip // empty' "$CONFIG_FILE" || echo "$SERVER_IP")
        APP_NAME=$(jq -r '.app_name // empty' "$CONFIG_FILE" || echo "$APP_NAME")
        BACKUP_DIR=$(jq -r '.backup_dir // empty' "$CONFIG_FILE" || echo "$BACKUP_DIR")
        SSH_USER=$(jq -r '.ssh_user // "root"' "$CONFIG_FILE")
        SSH_PORT=$(jq -r '.ssh_port // 22' "$CONFIG_FILE")
        API_PORT=$(jq -r '.api_port // 8000' "$CONFIG_FILE")
        FRONTEND_PORT=$(jq -r '.frontend_port // 5173' "$CONFIG_FILE")
    else
        log_warn "未找到jq命令，跳过配置文件读取，使用默认参数"
        SSH_USER="root"
        SSH_PORT=22
        API_PORT=8000
        FRONTEND_PORT=5173
    fi
else
    # 默认配置
    SSH_USER="root"
    SSH_PORT=22
    API_PORT=8000
    FRONTEND_PORT=5173
fi

# 如果命令行提供了服务器IP，则覆盖配置文件中的设置
if [ -n "$2" ] && [ "$2" != "your-server-ip" ]; then
    SERVER_IP="$2"
fi


# 检查参数
if [ -z "$SERVER_IP" ] || [ "$SERVER_IP" = "your-server-ip" ]; then
    log_error "请指定服务器IP地址: ./deploy.sh prod 1.2.3.4"
    exit 1
fi

# 步骤1: 本地代码打包
log_info "步骤1: 本地代码检查与打包..."

# 检查必要命令
required_commands=("ssh" "rsync")
for cmd in "${required_commands[@]}"; do
    if ! command -v "$cmd" &> /dev/null; then
        log_error "必要命令 '$cmd' 未找到，请安装后再运行"
        exit 1
    fi
done

# 检查必要文件
required_files=(
    "docker-compose.yml"
    "frontend-demo/Dockerfile"
    "backend/Dockerfile.dev"
    ".env"
)

for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        log_error "缺少必要文件: $file"
        exit 1
    fi
done

# 检查环境文件
if [ ! -f ".env" ]; then
    log_error "缺少.env文件，请根据.env.example创建配置"
    exit 1
fi

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# 步骤2: 数据库备份（如果已存在）
log_info "步骤2: 检查远程数据库备份..."
if ssh ${SSH_USER}@$SERVER_IP -p ${SSH_PORT} "docker ps | grep -q SoundVerse-mysql" 2>/dev/null; then
    log_info "检测到现有MySQL容器，执行备份..."

    # 创建备份
    BACKUP_FILE="${APP_NAME}_db_backup_${TIMESTAMP}.sql"
    ssh ${SSH_USER}@$SERVER_IP -p ${SSH_PORT} "docker exec SoundVerse-mysql mysqldump -u soundverse -ppassword soundverse --no-tablespaces > /tmp/${BACKUP_FILE} 2>/dev/null || true"

    # 下载备份
    scp -P ${SSH_PORT} ${SSH_USER}@$SERVER_IP:/tmp/${BACKUP_FILE} ${BACKUP_DIR}/${BACKUP_FILE}

    if [ -s "${BACKUP_DIR}/${BACKUP_FILE}" ]; then
        log_info "数据库备份完成: ${BACKUP_DIR}/${BACKUP_FILE}"
    else
        log_warn "数据库备份可能为空或失败"
    fi
fi

# 步骤3: SSH同步代码到服务器
log_info "步骤3: 同步代码到服务器 $SERVER_IP ..."

# 创建服务器目录结构
ssh ${SSH_USER}@$SERVER_IP -p ${SSH_PORT} "mkdir -p /opt/${APP_NAME}/{backend,frontend-demo,data}"

# 同步关键文件
rsync -avz --progress -e "ssh -p ${SSH_PORT}" \
    --exclude='.git' \
    --exclude='node_modules' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.env' \
    --exclude='.DS_Store' \
    ./ ${SSH_USER}@$SERVER_IP:/opt/${APP_NAME}/

# 上传环境文件（如果本地存在）
if [ -f ".env" ]; then
    scp -P ${SSH_PORT} .env ${SSH_USER}@$SERVER_IP:/opt/${APP_NAME}/.env
    log_info "已上传环境配置文件"
else
    log_warn "未找到.env文件，将使用服务器现有配置"
fi

# 步骤4: 远程构建与启动
log_info "步骤4: 在服务器上构建并启动服务..."

# 创建启动脚本
cat > /tmp/start_soundverse.sh << 'EOF'
#!/bin/bash
set -e

APP_NAME="soundverse-demo"
WORK_DIR="/opt/${APP_NAME}"

cd "$WORK_DIR"

# 检查Docker Compose是否可用
if ! command -v docker-compose &> /dev/null; then
    # 尝试使用docker compose插件
    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
    else
        echo "错误: 未找到docker-compose或docker compose插件"
        exit 1
    fi
else
    COMPOSE_CMD="docker-compose"
fi

# 停止现有服务
echo "停止现有服务..."
$COMPOSE_CMD down --remove-orphans || true

# 构建并启动新服务
echo "构建新服务..."
$COMPOSE_CMD build --no-cache

echo "启动服务..."
$COMPOSE_CMD up -d

# 等待服务就绪
echo "等待服务启动..."
sleep 10

# 检查服务状态
echo "服务状态:"
$COMPOSE_CMD ps

# 运行数据库迁移
echo "运行数据库迁移..."
$COMPOSE_CMD exec api python -c "
import asyncio
from shared.database.session import init_db
asyncio.run(init_db())
print('数据库初始化完成')
" || echo "数据库迁移可能失败，请手动检查"

# 初始化向量索引
echo "初始化向量索引..."
$COMPOSE_CMD exec api python -c "
import asyncio
from services.search_service import init_vector_index
asyncio.run(init_vector_index())
print('向量索引初始化完成')
" || echo "向量索引初始化可能失败，请手动检查"

echo "部署完成!"
EOF

# 上传并执行启动脚本
scp -P ${SSH_PORT} /tmp/start_soundverse.sh ${SSH_USER}@$SERVER_IP:/opt/${APP_NAME}/
ssh ${SSH_USER}@$SERVER_IP -p ${SSH_PORT} "chmod +x /opt/${APP_NAME}/start_soundverse.sh && cd /opt/${APP_NAME} && ./start_soundverse.sh"

# 步骤5: 健康检查
log_info "步骤5: 执行健康检查..."

# 检查前端服务
if curl -s -f "http://${SERVER_IP}:${FRONTEND_PORT}" > /dev/null; then
    log_info "前端服务健康: http://${SERVER_IP}:${FRONTEND_PORT}"
else
    log_warn "前端服务可能未启动，请检查"
fi

# 检查后端API
if curl -s -f "http://${SERVER_IP}:${API_PORT}/health" > /dev/null; then
    log_info "后端API健康: http://${SERVER_IP}:${API_PORT}/health"
else
    log_warn "后端API可能未启动，请检查"
fi

# 步骤6: 清理和报告
log_info "步骤6: 部署完成！"

echo ""
echo "================================"
echo "部署成功！"
echo "环境: $ENV"
echo "服务器: $SERVER_IP"
echo "前端访问: http://${SERVER_IP}:${FRONTEND_PORT}"
echo "后端API: http://${SERVER_IP}:${API_PORT}/docs"
echo "数据库备份: ${BACKUP_DIR}/"
echo "================================"
echo ""
echo "常用命令:"
echo "查看日志: ssh ${SSH_USER}@$SERVER_IP -p ${SSH_PORT} 'cd /opt/${APP_NAME} && docker-compose logs -f'"
echo "重启服务: ssh ${SSH_USER}@$SERVER_IP -p ${SSH_PORT} 'cd /opt/${APP_NAME} && docker-compose restart'"
echo "停止服务: ssh ${SSH_USER}@$SERVER_IP -p ${SSH_PORT} 'cd /opt/${APP_NAME} && docker-compose down'"
echo "更新代码: ./deploy.sh $ENV $SERVER_IP"
echo "================================"

rm -f /tmp/start_soundverse.sh