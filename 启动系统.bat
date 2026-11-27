@echo off
setlocal
cd /d "%~dp0"
set "MYSQL_BIN=D:\xueru\Documents\dsh work\_tmp\mysql84\mysql-8.4.3-winx64\bin"
set "MYSQL_HOME=D:\xueru\Documents\dsh work\_tmp\mysql84"

set "PY=%~dp0.venv\Scripts\python.exe"
if exist "%PY%" goto :deps_ok
echo [deps] venv not found, installing (first run, 1-2 min) ...
python -m venv "%~dp0.venv"
"%PY%" -m pip install -q -r "%~dp0requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple
:deps_ok
set "PORT=8021"

echo [1/3] Check MySQL 8.4 on port 3307 ...
netstat -ano | findstr ":3307" | findstr "LISTENING" >nul
if errorlevel 1 (
  echo     starting mysql ...
  start "MySQL 8.4" /min "%MYSQL_BIN%\mysqld.exe" --no-defaults --basedir="%MYSQL_HOME%\mysql-8.4.3-winx64" --datadir="%MYSQL_HOME%\data" --tmpdir="%MYSQL_HOME%\tmp" --port=3307 --bind-address=127.0.0.1 --mysqlx=0 --mysql-native-password=ON
  "%SystemRoot%\System32\timeout.exe" /t 8 /nobreak >nul
) else (
  echo     already running
)

echo [2/3] Check Django on port %PORT% ...
netstat -ano | findstr ":%PORT%" | findstr "LISTENING" >nul
if errorlevel 1 (
  echo     starting django ...
  start "Django %PORT%" /min "%PY%" manage.py runserver 127.0.0.1:%PORT% --noreload
  "%SystemRoot%\System32\timeout.exe" /t 5 /nobreak >nul
) else (
  echo     already running
)

echo [3/3] Open login page ...
start "" "http://127.0.0.1:%PORT%/login/"

echo.
echo Accounts: admin / Admin@2026    zhangsan / test123456
echo URL: http://127.0.0.1:%PORT%/login/
pause