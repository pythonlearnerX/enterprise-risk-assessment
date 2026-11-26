@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在打开答辩要用的 5 个代码文件...
where code >nul 2>nul
if errorlevel 1 (
    echo 未检测到 VS Code 命令行（code），改为直接打开文件夹。
    start "" "%CD%"
) else (
    start "" code risk_app\risk_calc.py risk_app\models.py risk_app\views.py risk_app\analytics.py risk_app\decorators.py
)
start "" "00-答辩导航.md"
echo.
echo 已打开：risk_calc.py / models.py / views.py / analytics.py / decorators.py
echo 站点：http://127.0.0.1:8021    （先运行 启动系统.bat）
pause
