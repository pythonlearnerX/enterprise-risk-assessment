@echo off
chcp 65001 >nul
rem 容器化：构建镜像 → 运行容器 → 健康检查（步骤 3、6）
cd /d "%~dp0"

echo === 0. 环境检查 ===
docker version >nul 2>&1
if errorlevel 1 (
  echo [X] 未检测到 Docker，请先安装并启动 Docker Desktop（需 WSL2 后端），再运行本脚本。
  exit /b 1
)

echo === 1. 构建镜像 nlp-risk:latest ===
docker build -t nlp-risk .
if errorlevel 1 ( echo [X] 镜像构建失败，看上面的报错 & exit /b 1 )

echo === 2. 清理同名旧容器 ===
docker rm -f nlp-risk >nul 2>&1

echo === 3. 运行容器（宿主 5000 → 容器 5000） ===
docker run -d -p 5000:5000 --name nlp-risk --restart unless-stopped nlp-risk
if errorlevel 1 ( echo [X] 容器启动失败：多半是 5000 端口被占用 & exit /b 1 )

echo === 4. 容器状态 ===
docker ps --filter name=nlp-risk --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}\t{{.Image}}"

echo === 5. 等待服务就绪后健康检查 ===
for /l %%i in (1,1,15) do (
  timeout /t 1 >nul
  curl -s http://127.0.0.1:5000/health | findstr "ok" >nul && (
    echo [OK] 健康检查通过： & curl -s http://127.0.0.1:5000/health
    goto done
  )
)
echo [X] 15 秒内健康检查未通过，请执行： docker logs nlp-risk
:done
echo.
echo 启动日志（前 20 行）： docker logs --tail 20 nlp-risk