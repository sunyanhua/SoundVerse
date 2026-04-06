"""
环境检查脚本 - 验证后端运行环境
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

# 优先加载 .env.local 文件
from dotenv import load_dotenv
env_local = Path(__file__).parent / ".env.local"
if env_local.exists():
    load_dotenv(env_local, override=True)
    print("[INFO] 已加载 .env.local 配置")
else:
    print("[WARN] 未找到 .env.local，使用默认配置")

async def check_database():
    """检查数据库连接"""
    try:
        from config import settings
        from shared.database.session import init_db, close_db

        print("[DB] 检查数据库连接...")
        print(f"     数据库URL: {settings.get_database_url()}")

        await init_db()
        print("     [OK] 数据库连接成功")

        # 测试查询
        from shared.database.session import async_session_maker
        from sqlalchemy import text

        async with async_session_maker() as session:
            result = await session.execute(text("SELECT 1"))
            result.scalar()  # scalar() 返回的是值，不需要 await
            print("     [OK] 数据库查询测试通过")

        await close_db()
        return True
    except Exception as e:
        print(f"     [FAIL] 数据库连接失败: {e}")
        return False

async def check_redis():
    """检查Redis连接"""
    try:
        from config import settings
        import redis.asyncio as redis

        print("[Redis] 检查Redis连接...")
        print(f"        Redis URL: {settings.get_redis_url()}")

        r = redis.from_url(settings.get_redis_url())
        await r.ping()
        print("        [OK] Redis连接成功")
        await r.close()
        return True
    except Exception as e:
        print(f"        [WARN] Redis连接失败: {e}")
        print("        [TIP] Redis用于缓存和Celery，非必需但建议安装")
        return False

async def check_oss():
    """检查OSS配置"""
    try:
        from config import settings

        print("[OSS] 检查OSS配置...")
        if settings.ALIYUN_ACCESS_KEY_ID and settings.ALIYUN_ACCESS_KEY_ID != 'your-access-key-id':
            print("      [OK] OSS AccessKey 已配置")
        else:
            print("      [WARN] OSS AccessKey 未配置")

        if settings.DASHSCOPE_API_KEY:
            print("      [OK] DashScope API Key 已配置")
        else:
            print("      [WARN] DashScope API Key 未配置")

        return True
    except Exception as e:
        print(f"      [FAIL] OSS配置检查失败: {e}")
        return False

async def check_auth_mode():
    """检查认证模式"""
    try:
        from config import settings

        print("[Auth] 检查认证配置...")
        print(f"       AUTH_MODE: {settings.AUTH_MODE}")

        if settings.AUTH_MODE == "demo":
            print("       [OK] Demo模式 - 免认证访问")
        else:
            print("       [INFO] JWT模式 - 需要认证token")

        return True
    except Exception as e:
        print(f"       [FAIL] 认证配置检查失败: {e}")
        return False

def main():
    print("=" * 50)
    print("SoundVerse 后端环境检查")
    print("=" * 50)
    print()

    results = []

    # 运行所有检查
    results.append(("认证配置", asyncio.run(check_auth_mode())))
    results.append(("数据库", asyncio.run(check_database())))
    results.append(("Redis", asyncio.run(check_redis())))
    results.append(("OSS", asyncio.run(check_oss())))

    print()
    print("=" * 50)
    print("检查结果汇总")
    print("=" * 50)

    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{name:12} {status}")

    print()

    # 检查是否有关键失败
    critical_failed = not results[0][1] or not results[1][1]  # 认证或数据库失败
    if critical_failed:
        print("[!] 关键检查未通过，请修复后再启动服务")
        print()
        print("常见问题:")
        print("1. 数据库连接失败: 检查MySQL是否运行，或修改.env.local使用SQLite")
        print("2. 认证配置错误: 确保AUTH_MODE=demo")
        sys.exit(1)
    else:
        print("[OK] 环境检查通过，可以启动后端服务")
        print()
        print("启动命令: .\\start_local.bat")
        sys.exit(0)

if __name__ == "__main__":
    main()
