#!/bin/bash
# 数据库初始化脚本
set -e

echo "🚀 开始初始化SoundVerse数据库..."

# 等待MySQL服务就绪
echo "⏳ 等待MySQL服务启动..."
while ! mysqladmin ping -h"mysql" -P"3306" -u"soundverse" -p"password" --silent; do
    echo "等待MySQL连接..."
    sleep 2
done

echo "✅ MySQL服务已就绪"

# 初始化Alembic（如果尚未初始化）
if [ ! -f "alembic.ini" ]; then
    echo "📦 初始化Alembic迁移配置..."
    alembic init alembic
    # 更新alembic.ini配置
    sed -i "s|sqlalchemy.url =.*|sqlalchemy.url = mysql://soundverse:password@mysql:3306/soundverse|" alembic.ini
    # 更新env.py以导入Base
    echo "import sys
import os
sys.path.append(os.getcwd())
from shared.database.session import Base
target_metadata = Base.metadata" > alembic/env.py.tmp
    # 保留原有内容，在target_metadata行后添加
    head -n $(grep -n "target_metadata = None" alembic/env.py | cut -d: -f1) alembic/env.py > alembic/env.py.new
    cat alembic/env.py.tmp >> alembic/env.py.new
    tail -n +$(( $(grep -n "target_metadata = None" alembic/env.py | cut -d: -f1) + 1 )) alembic/env.py >> alembic/env.py.new
    mv alembic/env.py.new alembic/env.py
    rm alembic/env.py.tmp
fi

# 创建初始迁移
echo "📝 创建初始数据库迁移..."
alembic revision --autogenerate -m "initial migration"

# 应用迁移
echo "🔧 应用数据库迁移..."
alembic upgrade head

echo "✅ 数据库初始化完成！"
echo "📊 数据库表已创建："
echo "   - users / user_tokens / user_usage"
echo "   - audio_sources / audio_segments / favorite_segments"
echo "   - chat_sessions / chat_messages / generated_audios"