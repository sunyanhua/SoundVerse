@echo off
chcp 65001 >nul
echo ============================================
echo SoundVerse 后端本地启动脚本
echo ============================================
echo.

REM 检查Python版本
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请安装Python 3.11+
    exit /b 1
)

REM 安装/更新依赖
echo [1/3] 安装依赖...
pip install -e ".[dev]" -q
if errorlevel 1 (
    echo [错误] 依赖安装失败
    exit /b 1
)

REM 加载本地环境配置
echo [2/3] 加载环境配置 (.env.local)...
if not exist .env.local (
    echo [警告] 未找到.env.local，使用默认.env配置
)

REM 启动服务
echo [3/3] 启动后端服务...
echo.
echo 服务将启动在: http://localhost:8000
echo API文档: http://localhost:8000/docs
echo 健康检查: http://localhost:8000/health
echo.
echo 按Ctrl+C停止服务
echo ============================================

REM 使用本地配置启动
if exist .env.local (
    uvicorn main:app --reload --host 0.0.0.0 --port 8000 --env-file .env.local
) else (
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
)
