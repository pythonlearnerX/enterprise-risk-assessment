@echo off
chcp 65001 >nul
title 安装 Docker Desktop（管理员）
rem 双击后自动申请管理员权限，然后调用 install_docker_fast.ps1
rem 只做：启用 WSL2 两个功能 + 装本地 WSL2 内核 + 装/跳过 Docker

net session >nul 2>&1
if errorlevel 1 (
  echo [*] 当前不是管理员，正在弹 UAC 申请提权，请点「是」...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

echo ============================================================
echo   Docker + WSL2 安装（管理员模式已确认）
echo ============================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_docker_fast.ps1"

echo.
echo 若上面没有报错，请重启电脑，然后启动 Docker Desktop 等它变成 Engine running。
pause