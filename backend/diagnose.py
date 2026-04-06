"""
后端诊断脚本 - 检查 AUTH_MODE 配置
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# 强制加载 .env.local
from dotenv import load_dotenv
env_local = Path(__file__).parent / ".env.local"
if env_local.exists():
    load_dotenv(env_local, override=True)
    print(f"[INFO] 已加载: {env_local}")

from config import settings

print(f"\n当前配置:")
print(f"  AUTH_MODE: {settings.AUTH_MODE}")
print(f"  ENVIRONMENT: {settings.ENVIRONMENT}")
print(f"  DEBUG: {settings.DEBUG}")

if settings.AUTH_MODE == "demo":
    print("\n[OK] 认证模式正确: demo (免认证)")
else:
    print(f"\n[WARN] 认证模式是: {settings.AUTH_MODE}")
    print("     需要设置为 demo 才能免认证访问")

# 测试模拟用户创建
async def test_mock_user():
    from shared.database.session import init_db, async_session_maker
    from api.v1.auth import get_or_create_mock_user

    print("\n测试模拟用户创建...")
    try:
        await init_db()
        async with async_session_maker() as db:
            user = await get_or_create_mock_user(db)
            print(f"  [OK] 模拟用户: {user.id}, {user.nickname}")
    except Exception as e:
        print(f"  [ERROR] {e}")

asyncio.run(test_mock_user())
