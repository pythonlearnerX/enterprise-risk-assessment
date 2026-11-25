@echo off
chcp 65001 >nul
rem 项目 15：Docker 环境自检。装完 Docker Desktop 后先跑这个，再跑 build_and_run.bat
echo ============================================================
echo   Docker 环境自检（项目 15 · NLP 微服务）
echo ============================================================
echo.

echo [1] docker 命令是否存在
where docker >nul 2>&1
if errorlevel 1 (
  echo     [X] 找不到 docker.exe：Docker Desktop 未安装或未加入 PATH
  echo         安装后在「开始菜单」启动一次 Docker Desktop，等托盘图标变绿
) else (
  where docker
  docker --version
)
echo.

echo [2] Docker 引擎是否在运行
docker info --format "     Server: {{.ServerVersion}} | OS: {{.OperatingSystem}} | 容器数: {{.Containers}}" >nul 2>&1
if errorlevel 1 (
  echo     [X] 引擎未就绪：Docker Desktop 没启动，或 WSL2 后端异常
  echo         排查：托盘图标右键 -> Troubleshoot；或 PowerShell 执行 wsl --status
) else (
  docker info --format "     Server: {{.ServerVersion}} | OS: {{.OperatingSystem}} | 容器数: {{.Containers}}"
)
echo.

echo [3] WSL2 状态
wsl --status
echo.
echo     已安装发行版：
wsl -l -v
echo.

echo [4] 宿主机 5000 端口占用（应为空，容器要用它）
netstat -ano | findstr ":5000" | findstr "LISTENING"
if errorlevel 1 (echo     [OK] 5000 未被占用) else (echo     [!] 5000 已被占用，先停掉占用进程，或用 -p 5001:5000)
echo.

echo [5] 已有的 nlp-risk 镜像 / 容器
docker images 2>nul | findstr "nlp-risk"
if errorlevel 1 (echo     尚无 nlp-risk 镜像，需要 build) else (echo     ^^ 已有镜像)
docker ps -a 2>nul | findstr "nlp-risk"
if errorlevel 1 (echo     尚无 nlp-risk 容器) else (echo     ^^ 已有容器)
echo.

echo [6] 服务健康检查（容器在跑时才有输出）
curl -s --max-time 3 http://127.0.0.1:5000/health
echo.
echo ============================================================
echo   全部通过后执行： build_and_run.bat
echo ============================================================