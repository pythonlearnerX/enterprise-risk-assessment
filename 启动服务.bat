@echo off
rem Risk assessment system - background services (autostart, no browser)
cd /d "%~dp0"
set "MYSQL_BIN=D:\xueru\Documents\dsh work\_tmp\mysql84\mysql-8.4.3-winx64\bin\mysqld.exe"
set "MYSQL_HOME=D:\xueru\Documents\dsh work\_tmp\mysql84"

netstat -ano | findstr ":3307" | findstr "LISTENING" >nul
if errorlevel 1 (
  start "MySQL84" /min "%MYSQL_BIN%" --no-defaults --basedir="%MYSQL_HOME%\mysql-8.4.3-winx64" --datadir="%MYSQL_HOME%\data" --tmpdir="%MYSQL_HOME%\tmp" --port=3307 --bind-address=127.0.0.1 --mysqlx=0 --mysql-native-password=ON
)

rem wait up to 30s for mysql
for /l %%i in (1,1,30) do (
  netstat -ano | findstr ":3307" | findstr "LISTENING" >nul
  if not errorlevel 1 goto mysql_ready
  "%SystemRoot%\System32\timeout.exe" /t 1 /nobreak >nul
)
:mysql_ready

netstat -ano | findstr ":8021" | findstr "LISTENING" >nul
if errorlevel 1 (
  start "Django8021" /min "%~dp0.venv\Scripts\python.exe" manage.py runserver 127.0.0.1:8021 --noreload
)