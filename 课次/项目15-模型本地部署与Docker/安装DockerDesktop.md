# 安装 Docker Desktop（本机专用步骤）

> 目标：装好后能跑 `nlp_service\build_and_run.bat`，把项目 15 的容器层验证补齐。
> 本机结论先说：**能装，走 WSL2 后端**。Windows 11 家庭版不支持 Hyper-V，但 WSL2 后端不需要 Hyper-V。

## 一、本机现状（已实测）

| 项 | 值 | 对安装的影响 |
| --- | --- | --- |
| 系统 | Windows 11 家庭版 China，10.0.26100（24H2） | 家庭版 → 必须用 WSL2 后端，不能用 Hyper-V 后端 |
| CPU | AMD Ryzen 7 7435H（8 核 16 线程） | 足够 |
| 虚拟化 | **固件已开启**（Virtualization Enabled In Firmware: Yes，SLAT: Yes，DEP: Yes） | 不用进 BIOS 改设置 |
| 内存 | 15.7 GB，当前空闲约 5.9 GB | 建议给 WSL 设上限，别让它吃满 |
| C 盘 | 101 GB，剩 22 GB | 够装，但**镜像数据要搬到 D 盘** |
| WSL | 未安装任何发行版 | 需要先开 WSL2 |
| 当前会话 | 无管理员权限 | 下面带 ⚠ 的命令要你自己用**管理员**窗口执行 |

## 二、四步装完

### 第 1 步：开 WSL2（需要管理员，需重启一次）

1. 开始菜单搜 **PowerShell** → 右键 **以管理员身份运行**；
2. 执行（只装 WSL 内核与虚拟机平台，不装 Ubuntu，Docker 会用自己的发行版）：

```powershell
wsl --install --no-distribution
```

3. 看到 `已安装...请重新启动计算机` 后**重启电脑**；
4. 重启后打开普通 PowerShell 验证：

```powershell
wsl --status      # 应显示 默认版本: 2
wsl --update      # 顺手更新内核，避免 Docker 报 "WSL kernel version too low"
```

> 如果 `wsl --install` 报「无法解析服务器名称」或下载失败：
> 打开「启用或关闭 Windows 功能」，勾选 **适用于 Linux 的 Windows 子系统** 和 **虚拟机平台**，确定后重启，
> 再执行 `wsl --update`。

### 第 2 步：安装 Docker Desktop（需要管理员确认）

**方式 A：winget（推荐，一条命令）**

管理员 PowerShell：

```powershell
winget install -e --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements
```

**方式 B：安装包（我已下到 D 盘，省下载时间）**

```
D:\xueru\Documents\dsh work\_tmp\docker_installer\DockerDesktopInstaller.exe
```

右键 → **以管理员身份运行**。安装界面：

- ✅ 勾选 **Use WSL 2 instead of Hyper-V (recommended)**
- ✅ 勾选 **Add shortcut to desktop**
- 安装完成点 **Close and restart**（会注销一次）

### 第 3 步：首次启动与设置（关键，别跳过）

1. 从开始菜单启动 **Docker Desktop**，接受服务协议；
2. 出现登录界面时点 **Skip / Continue without signing in**（课程不需要账号）；
3. 等左下角状态变成 **Engine running**（绿色），托盘鲸鱼图标不再转圈；
4. **把镜像数据搬到 D 盘**（否则 C 盘会被吃掉十几 G）：
   `Settings`（右上齿轮）→ `Resources` → `Advanced` → `Disk image location` 改成
   `D:\DockerData` → `Apply & restart`；
5. 顺手限制内存（可选，本机只空闲 5.9 GB）：
   在 `%USERPROFILE%\.wslconfig` 写入下面内容，然后 `wsl --shutdown` 再重启 Docker：

```ini
[wsl2]
memory=6GB
processors=6
swap=2GB
```

### 第 4 步：验证装好了

普通 PowerShell（新开一个）依次执行：

```powershell
docker --version                 # Docker version 2x.x.x
docker info --format "{{.ServerVersion}}"
docker run --rm hello-world      # 打印 Hello from Docker! 即成功
```

再跑项目自检脚本（会把 docker / WSL / 5000 端口 / 镜像 / 健康检查一次看完）：

```bat
cd /d "D:\xueru\Documents\dsh work\03_项目\risk_project_xuerui\nlp_service"
docker_env_check.bat
```

## 三、装完怎么补齐项目 15

```bat
cd /d "D:\xueru\Documents\dsh work\03_项目\risk_project_xuerui\nlp_service"
build_and_run.bat
```

脚本会：构建镜像 → 删同名旧容器 → `docker run -d -p 5000:5000` → 轮询 `/health` 直到通过 → 打印容器状态。

然后回到系统页面 `http://127.0.0.1:8021/model/show/`，点「开始识别」；
再执行 `docker stop nlp-risk` 点一次（应是降级提示）、`docker start nlp-risk` 点一次（应恢复）。

补齐后把输出发我，我把 `docker build` / `docker ps` / `docker logs` 三张截图补进
`课次/项目15-模型本地部署与Docker/截图/`，并把验证表 V-01/V-06/V-07/V-08 改成 ✅。

## 四、常见问题对照

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| Docker Desktop 启动转圈不止 / 报 `WSL 2 installation is incomplete` | WSL 内核没装或版本太低 | 管理员执行 `wsl --update`，再重启 Docker |
| 报 `Hardware assisted virtualization... not enabled` | BIOS 虚拟化没开 | 本机已开；若换机器：BIOS 里开 SVM/VT-x |
| 报 `Virtual Machine Platform not enabled` | 第 1 步没做或没重启 | 功能里勾「虚拟机平台」→ 重启 |
| `docker` 命令找不到 | PATH 没生效 | 关掉终端重开；或重启一次 |
| 拉基础镜像超时（`docker build` 卡在 pulling） | Docker Hub 受限 | 本项目 Dockerfile 已用华为云同步地址，通常不用改；仍超时则在 Settings → Docker Engine 加 `"registry-mirrors": ["https://docker.m.daocloud.io"]` |
| `port is already allocated` | 5000 被占 | `docker ps -a` 清旧容器；或改 `-p 5001:5000` 并同步改 `NLP_SERVICE_URL` |
| 容器起来就退出 | 启动命令报错 | `docker logs nlp-risk` 看栈 |
| C 盘突然少十几 G | 镜像数据默认在 C | 第 3 步第 4 点把 Disk image location 改到 D |
| 编译时整机卡顿 | WSL 吃满内存 | 用上面的 `.wslconfig` 限 6GB，`wsl --shutdown` 后重启 Docker |
| 提示需要登录 Docker 账号 | 新版首启流程 | 点 Skip，可离线使用 |

## 五、许可与合规

Docker Desktop 对个人使用、教育用途、小型企业（<250 员工且年收入 <1000 万美元）免费；
课程实训属于教育用途，直接用没问题。若要长期跑在服务器上，应改用 Docker Engine（Linux）而不是 Desktop。

## 六、如果实在装不上（备用方案）

`nlp_service\run_local.bat` 用本机 Python 直接跑同一个 `app.py`，接口、Django 集成、页面、
降级演练全部可用——区别只是**没有镜像与容器**，因此 V-01/V-06/V-07/V-08 四条容器层验证无法完成。
答辩时如实说明即可：代码与接口已跑通，容器化受本机环境限制。

## 七、`wsl --install` 下载太慢怎么办（2026-11-23 实测）

**现象**：管理员窗口执行 `wsl --install --no-distribution` 后卡在

```
正在下载: 适用于 Linux 的 Windows 子系统 3.0.5
[====                          5.3%                        ]
```

**原因**：这一步要从微软商店 CDN 拉 WSL 的 MSIX 包，本机实测该 CDN 只有 **约 50 KB/s**
（同时测了 16 MB 的 WSL2 内核 MSI，用了约 5 分钟），12 分钟才走到 5.3%，按这个速度要几个小时。
顺带测了 GitHub（通常更快的源）——**连不上**（curl 超时）；而 `desktop.docker.com`
下载 595 MB 的 Docker 安装包只用了 3 分半（约 2.8 MB/s）。

**结论：不要等商店包，改走「全本地」路线**，只用系统内置文件 + 已下好的两个安装包：

```powershell
# 1) 先在原来的窗口按 Ctrl+C 掐掉慢下载
# 2) 同一个管理员窗口执行：
powershell -ExecutionPolicy Bypass -File "D:\xueru\Documents\dsh work\03_项目\risk_project_xuerui\nlp_service\install_docker_fast.ps1"
```

该脚本做的四件事（都不联网）：

| 步骤 | 命令 | 耗时 |
| --- | --- | --- |
| 启用「适用于 Linux 的 Windows 子系统」 | `dism /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart` | 秒级 |
| 启用「虚拟机平台」 | `dism /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart` | 秒级 |
| 装 WSL2 内核 | `msiexec /i wsl_update_x64.msi /qn`（16 MB，已在本地） | 约 30 秒 |
| 静默装 Docker Desktop | `DockerDesktopInstaller.exe install --quiet --accept-license --backend=wsl-2` | 3–8 分钟 |

装完**重启**，之后按第三节第 3、4 步做设置即可。

> 若重启后 Docker 报「WSL kernel version too low」，再执行一次 `wsl --update`——
> 那条只能联网下载，慢，但可以后台挂着，不影响 Docker 已装好的事实。

## 八、本地离线包清单（都在 `_tmp/docker_installer/`）

| 文件 | 大小 | 来源 | 校验 |
| --- | --- | --- | --- |
| `DockerDesktopInstaller.exe` | 623,969,712 字节（595 MB） | desktop.docker.com 官方 | 与服务器 `Content-Length` 一致；SHA256 `a5e29913…6cea444` |
| `wsl_update_x64.msi` | 17,104,896 字节（16 MB） | wslstorestorage.blob.core.windows.net 官方 | 官方直链下载 |

> 两个安装包都能删：装完 Docker 后 `_tmp/docker_installer/` 占 611 MB，确认能跑就可以清掉。

## 九、实际完成记录（2026-11-23，走过的真实路径）

按时间顺序记录，留给后面复盘：

| 时间 | 动作 | 结果 |
| --- | --- | --- |
| 09:35 | 下载 `DockerDesktopInstaller.exe`（595 MB） | ✅ docker.com 2.8 MB/s，3 分半；SHA256 与官方一致 |
| 10:06 | `wsl --install --no-distribution` | ❌ 卡在商店 CDN，12 分钟 5.3% |
| 10:16 | 下 `wsl_update_x64.msi`（16 MB 旧内核） | ⚠️ 下了，但**装不上**（msiexec 1603），24H2 已淘汰这条路 |
| 10:28 | `dism` 启用两个 Windows 功能 | ✅ 两条都是 `操作成功完成`，CBS 状态 `Installed` |
| 10:31 | 重启 | ✅ `vmcompute` 出现，但 `LxssManager` 仍缺 → 说明还差 WSL 应用包本身 |
| 10:34 | `wsl --status` | ❌ “未安装适用于 Linux 的 Windows 子系统” |
| 10:46 | GitHub 直连 / 多个加速代理测速 | ❌ 直连超时，代理 0–28 KB/s |
| 10:48 | **16 线程分块 + 代理**下 WSL 3.0.5 MSI（350 MB） | ✅ **90 秒**，367,788,032 字节与 Content-Length 一致 |
| 11:06 | `msiexec /i wsl.3.0.5.0.x64.msi` | ✅ `wsl --version` 显示 3.0.5.0 / 内核 6.18.58.1-1 |
| 11:00 | 启动 Docker Desktop | ✅ 引擎 29.9.3 就绪 |
| 11:01 | `docker pull` 华为云 `python:3.10-slim` | ✅ Docker Hub 直连超时，镜像源有效 |
| 11:01 | `docker build -t nlp-risk .` | ✅ 6 分 20 秒（pip 356 秒），镜像 198 MB |
| 11:02 | `docker run -d -p 5000:5000` | ✅ Up (healthy)，八项验证全绿 |

**结论（给以后装机器的人）**：

1. Windows 11 家庭版必须走 WSL2 后端，Hyper-V 不可用；
2. 24H2 的 WSL 由**应用包**提供，光启用功能不够，旧内核 MSI 是死路；
3. 微软商店 CDN 在这条网络下 50 KB/s，GitHub 直连不通，**分块并发下载**是有效手段（16 线程从 28 KB/s 提到 ~4 MB/s）；
4. Docker Hub 不通不影响本项目，Dockerfile 里已用华为云镜像源；但要跑 `hello-world` 之类拉 hub 镜像会失败；
5. `docker compose` 里的 `NLP_SERVICE_URL=http://nlp:5000` 只在编排内有效，宿主机直跑仍是 `127.0.0.1:5000`。
