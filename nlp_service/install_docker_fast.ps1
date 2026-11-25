# 项目 15：快速安装 WSL2 + Docker Desktop（全程用本地文件，不走商店下载）
# 为什么有这个脚本：`wsl --install` 要从微软商店 CDN 拉 WSL 包，本机实测约 50 KB/s，
# 5.3% 用了 12 分钟，等完要好几个小时。本脚本改用三个本地/离线来源：
#   ① DISM 启用两个 Windows 功能（文件在系统里，不需下载）
#   ② 本地 wsl_update_x64.msi（16 MB，已下好）装 WSL2 内核
#   ③ 本地 DockerDesktopInstaller.exe（595 MB，已下好）静默安装
# 用法（管理员 PowerShell）：
#   powershell -ExecutionPolicy Bypass -File "D:\xueru\Documents\dsh work\03_项目\risk_project_xuerui\nlp_service\install_docker_fast.ps1"

$ErrorActionPreference = "Continue"
function Info($m) { Write-Host "[*] $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "[OK] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "[!] $m" -ForegroundColor Yellow }
function Err($m)  { Write-Host "[X] $m" -ForegroundColor Red }

$KernelMsi = "D:\xueru\Documents\dsh work\_tmp\docker_installer\wsl_update_x64.msi"
$DockerExe = "D:\xueru\Documents\dsh work\_tmp\docker_installer\DockerDesktopInstaller.exe"

# ---------- 0. 管理员 ----------
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Err "当前不是管理员窗口。请：开始菜单搜 PowerShell -> 右键『以管理员身份运行』-> 再执行本脚本。"
    exit 1
}
Ok "管理员权限已确认"

# ---------- 1. 本地文件检查 ----------
if (-not (Test-Path $KernelMsi)) { Err "缺少 WSL2 内核包：$KernelMsi"; exit 1 }
if (-not (Test-Path $DockerExe)) { Err "缺少 Docker 安装包：$DockerExe"; exit 1 }
Ok ("本地安装包齐备：" + [math]::Round((Get-Item $KernelMsi).Length/1MB,1) + " MB + " + [math]::Round((Get-Item $DockerExe).Length/1MB,0) + " MB")

# ---------- 2. 启用两个 Windows 功能（本地操作，不下载） ----------
Info "启用『适用于 Linux 的 Windows 子系统』..."
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart | Select-String -Pattern "操作成功完成|The operation completed successfully|错误|Error" | Select-Object -First 2

Info "启用『虚拟机平台』（WSL2 依赖）..."
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart | Select-String -Pattern "操作成功完成|The operation completed successfully|错误|Error" | Select-Object -First 2

# ---------- 3. 安装 WSL2 内核（本地 MSI） ----------
Info "安装 WSL2 内核（wsl_update_x64.msi）..."
$p = Start-Process msiexec.exe -ArgumentList "/i `"$KernelMsi`" /qn /norestart" -Wait -PassThru
if ($p.ExitCode -eq 0 -or $p.ExitCode -eq 3010) { Ok "内核安装完成（3010 = 需重启，正常）" }
else { Warn "msiexec 返回 $($p.ExitCode)，可稍后手动双击该 MSI" }

# ---------- 4. 安装 Docker Desktop（本地 exe，WSL2 后端） ----------
Info "静默安装 Docker Desktop（WSL2 后端，约 3-8 分钟，无输出是正常现象）..."
$p2 = Start-Process -FilePath $DockerExe `
    -ArgumentList "install", "--quiet", "--accept-license", "--backend=wsl-2" `
    -Wait -PassThru
if ($p2.ExitCode -eq 0) { Ok "Docker Desktop 安装完成" }
else { Warn "安装程序返回 $($p2.ExitCode)；若已装好可忽略，否则双击安装包手动装" }

# ---------- 5. 后续 ----------
Write-Host ""
Write-Host "================ 现在必须重启 ================" -ForegroundColor Cyan
Write-Host " 两个 Windows 功能要重启才生效，Docker 也要等重启后初始化。"
Write-Host ""
Write-Host " 重启后："
Write-Host "  1) 开始菜单启动 Docker Desktop，登录界面点 Skip，等左下角 Engine running"
Write-Host "  2) Settings -> Resources -> Advanced -> Disk image location 改到 D:\DockerData"
Write-Host "  3) 普通 PowerShell 跑："
Write-Host "     cd /d `"D:\xueru\Documents\dsh work\03_项目\risk_project_xuerui\nlp_service`""
Write-Host "     docker_env_check.bat"
Write-Host "     build_and_run.bat"
Write-Host ""
Write-Host " 若 Docker 提示 WSL 版本过低，再单独执行 wsl --update（那个只能联网下，慢，但可后台挂着）"
Write-Host "=============================================" -ForegroundColor Cyan