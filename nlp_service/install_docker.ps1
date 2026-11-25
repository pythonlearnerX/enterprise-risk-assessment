# 项目 15：一键安装 WSL2 + Docker Desktop（需要管理员）
# 用法（管理员 PowerShell）：
#   powershell -ExecutionPolicy Bypass -File "D:\xueru\Documents\dsh work\03_项目\risk_project_xuerui\nlp_service\install_docker.ps1"
# 说明：本脚本只做三件事 —— 开 WSL2、装 Docker Desktop、打印后续步骤；不改其它系统设置。

$ErrorActionPreference = "Continue"
function Info($m) { Write-Host "[*] $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "[OK] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "[!] $m" -ForegroundColor Yellow }
function Err($m)  { Write-Host "[X] $m" -ForegroundColor Red }

# ---------- 0. 必须管理员 ----------
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Err "当前不是管理员窗口，安装会被系统拒绝。"
    Write-Host ""
    Write-Host "请这样重新打开：" -ForegroundColor Yellow
    Write-Host "  1) 开始菜单搜索 PowerShell"
    Write-Host "  2) 右键 -> 以管理员身份运行"
    Write-Host "  3) 执行："
    Write-Host "     powershell -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit 1
}
Ok "管理员权限已确认"

# ---------- 1. 检查虚拟化 ----------
Info "检查 CPU 虚拟化（BIOS 设置）..."
$cs = Get-CimInstance Win32_ComputerSystem
if ($cs.HypervisorPresent) {
    Ok "已检测到 Hypervisor（虚拟化在用）"
} else {
    $vt = (systeminfo) -join "`n"
    if ($vt -match "Virtualization Enabled In Firmware:\s+Yes" -or $vt -match "固件中已启用虚拟化:\s+是") {
        Ok "固件虚拟化已启用（无需进 BIOS）"
    } else {
        Warn "未确认固件虚拟化，若后续报 'virtualization not enabled' 需进 BIOS 打开 SVM/VT-x"
    }
}

# ---------- 2. 开 WSL2 ----------
Info "检查 WSL 状态..."
$wslStatus = (wsl --status 2>&1 | Out-String)
if ($wslStatus -match "默认版本:\s*2" -or $wslStatus -match "Default Version:\s*2") {
    Ok "WSL2 已就绪，跳过安装"
} else {
    Info "执行 wsl --install --no-distribution（只装内核与虚拟机平台，不装 Ubuntu）"
    wsl --install --no-distribution
    if ($LASTEXITCODE -ne 0) {
        Warn "wsl --install 返回 $LASTEXITCODE，尝试启用两个 Windows 功能后再说："
        dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart | Out-Null
        dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart | Out-Null
    }
    Warn "WSL2 已提交安装，**必须重启一次**才能生效"
}

# ---------- 3. 安装 Docker Desktop ----------
Info "检查 Docker 是否已安装..."
$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if ($dockerCmd) {
    Ok "已检测到 docker：$($dockerCmd.Source)"
    docker --version
} else {
    $installer = "D:\xueru\Documents\dsh work\_tmp\docker_installer\DockerDesktopInstaller.exe"
    if (Test-Path $installer) {
        Info "使用已下载的安装包静默安装（WSL2 后端）..."
        Start-Process -FilePath $installer `
            -ArgumentList "install", "--quiet", "--accept-license", "--backend=wsl-2" `
            -Wait
        if ($LASTEXITCODE -eq 0) { Ok "Docker Desktop 安装完成" }
        else { Warn "安装程序返回 $LASTEXITCODE，请手动双击安装包确认" }
    } else {
        Info "安装包不存在，改用 winget 安装..."
        winget install -e --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements
    }
}

# ---------- 4. 后续步骤 ----------
Write-Host ""
Write-Host "================ 接下来的 3 步 ================" -ForegroundColor Cyan
Write-Host "1) 重启电脑（WSL2 生效 + 完成 Docker 安装）"
Write-Host "2) 重启后从开始菜单启动 Docker Desktop，等左下角变 Engine running；"
Write-Host "   登录界面点 Skip；Settings -> Resources -> Advanced -> Disk image location 改到 D:\DockerData"
Write-Host "3) 回到项目跑验证："
Write-Host "   cd /d `"D:\xueru\Documents\dsh work\03_项目\risk_project_xuerui\nlp_service`""
Write-Host "   docker_env_check.bat"
Write-Host "   build_and_run.bat"
Write-Host "=============================================" -ForegroundColor Cyan