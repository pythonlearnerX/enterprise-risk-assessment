@echo off
chcp 65001 >nul
rem 本地直接运行 NLP 微服务（不经容器，用于步骤 2 的本地验证）
cd /d "%~dp0"
echo [1/2] 检查依赖...
"..\.venv\Scripts\python.exe" -c "import flask, jieba" 2>nul
if errorlevel 1 (
  echo 缺少 flask / jieba，正在安装...
  "..\.venv\Scripts\python.exe" -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
)
echo [2/2] 启动服务： http://127.0.0.1:5000/health
"..\.venv\Scripts\python.exe" app.py