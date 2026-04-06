@echo off
chcp 65001 >nul
echo ============================================
echo SoundVerse Docker 本地部署脚本
echo ============================================
echo.

REM 检查 Docker
docker --version >nul 2>&1
if errorlevel 1 (
    echo [错误] Docker 未安装或未启动
    echo 请先安装 Docker Desktop: https://www.docker.com/products/docker-desktop
    exit /b 1
)

echo [OK] Docker 已安装

REM 检查环境文件
if not exist .env (
    if exist .env.example (
        echo [WARN] 未找到 .env 文件，复制示例配置...
        copy .env.example .env
        echo [WARN] 请编辑 .env 文件配置实际参数
    )
)

echo.
echo 请选择部署模式:
echo   1. 开发模式 (docker-compose.yml) - 支持热重载
echo   2. 生产模式 (docker-compose.prod.yml) - 性能优化
echo.
set /p choice="输入选择 (1/2): "

if "%choice%"=="1" (
    set COMPOSE_FILE=docker-compose.yml
    echo [INFO] 使用开发模式
) else (
    set COMPOSE_FILE=docker-compose.prod.yml
    echo [INFO] 使用生产模式
)

echo.
echo [1/4] 拉取基础镜像...
docker-compose -f %COMPOSE_FILE% pull

echo.
echo [2/4] 构建服务镜像...
docker-compose -f %COMPOSE_FILE% build

echo.
echo [3/4] 启动服务...
docker-compose -f %COMPOSE_FILE% up -d

echo.
echo [4/4] 等待服务就绪...
timeout /t 10 /nobreak >nul

echo.
echo ============================================
echo 服务状态检查
echo ============================================

REM 检查后端
curl -s http://localhost:8000/health >nul 2>&1
if %errorlevel%==0 (
    echo [OK] 后端 API: http://localhost:8000
    echo       文档: http://localhost:8000/docs
) else (
    echo [WARN] 后端 API 启动中，请稍后检查...
)

REM 检查前端
curl -s http://localhost:5173 >nul 2>&1
if %errorlevel%==0 (
    echo [OK] 前端页面: http://localhost:5173
) else (
    echo [WARN] 前端页面启动中，请稍后检查...
)

echo.
echo ============================================
echo 部署完成！
echo ============================================
echo.
echo 常用命令:
echo   查看日志: docker-compose -f %COMPOSE_FILE% logs -f
echo   停止服务: docker-compose -f %COMPOSE_FILE% down
echo   重启服务: docker-compose -f %COMPOSE_FILE% restart
echo   更新代码: docker-compose -f %COMPOSE_FILE% build --no-cache ^&^& docker-compose -f %COMPOSE_FILE% up -d
echo.
pause
