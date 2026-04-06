#!/bin/bash
set -e

echo "========================================"
echo "SoundVerse 后端启动脚本"
echo "========================================"

# 检查环境变量
echo "当前配置:"
echo "  AUTH_MODE: ${AUTH_MODE:-未设置}"
echo "  ENVIRONMENT: ${ENVIRONMENT:-未设置}"

# 等待数据库就绪
echo "等待数据库连接..."
python -c "
import asyncio
import sys
from sqlalchemy import text
from shared.database.session import init_db, async_session_maker

async def wait_for_db():
    max_retries = 30
    for i in range(max_retries):
        try:
            await init_db()
            async with async_session_maker() as session:
                result = await session.execute(text('SELECT 1'))
                await result.scalar()
                print('[OK] 数据库连接成功')
                return True
        except Exception as e:
            print(f'[WAIT] 数据库连接中... ({i+1}/{max_retries})')
            await asyncio.sleep(2)
    print('[ERROR] 数据库连接失败')
    return False

if not asyncio.run(wait_for_db()):
    sys.exit(1)
"

echo "启动 Uvicorn 服务..."
# 根据环境选择启动方式
if [ "$ENVIRONMENT" = "development" ]; then
    echo "开发模式: 启用热重载"
    exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload
else
    echo "生产模式: 多工作进程"
    exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
fi
