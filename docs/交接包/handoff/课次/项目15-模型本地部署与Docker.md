# 项目 15：模型本地部署与前端展示（Docker）

## 一、基本信息

| 项 | 内容 |
| --- | --- |
| 课次 | 项目 15（第 4 周 课次 17~18，8 学时） |
| 日期 | 2026-11-23 |
| 指导书 | `docs/参考资料/实训指导书_15_模型本地部署与前端展示（Docker）.docx` |
| 状态 | **全部完成**：代码、前端、容器化、八项验证与故障演练均为实测（见第十一节） |
| 产出 | `nlp_service/`、`risk_app/nlp_infer.py`、`model_show.html`、`docker-compose.yml`、3 张截图 |

## 二、九步走对照（先说本地，再容器化）

| 步 | 内容 | 状态 | 证据 |
| --- | --- | --- | --- |
| ① | 写服务代码：词库 + 评分 + 两个接口 | 完成 | `nlp_service/app.py`（150 行） |
| ② | 本地直跑 + curl 验证两个接口 | **完成（真实输出）** | `截图/03-本地运行与接口验证.png` |
| ③ | 写 Dockerfile（基础镜像/依赖/端口/启动） | **完成并构建成功** | `nlp_service/Dockerfile` |
| ④ | `docker build -t nlp-risk .` | **完成**（镜像 198 MB，ID 1cde466c1c32） | `截图/04` |
| ⑤ | `docker run -d -p 5000:5000 --name nlp-risk` | **完成**（Up healthy） | `截图/04` |
| ⑥ | 健康检查 `/health` | 完成（宿主机端口层） | 截图 03 第一段 |
| ⑦ | Django 集成：超时、降级、结果转换 | 完成 | `risk_app/nlp_infer.py` + 7 个测试 |
| ⑧ | 前端展示：分数、四维、关键词、高亮 | 完成 | `截图/01-页面识别结果.png` |
| ⑨ | 故障演练：停服务、端口占用、无镜像、改词库重建 | **全部完成** | `截图/05` |

> 顺序红线：②必须早于③④。本机先按②跑通接口、再接 Django，最后才写 Dockerfile ——
> 这样如果容器里报错，可以直接用「宿主机同一个 app.py 能跑」排除代码问题。

## 三、实现要点

### 1. 微服务（`nlp_service/app.py`）

- 四类词库共 35 个词，权重 6–10；每类得分累加封顶 100；
- 综合分 = 合规 40% + 财务 30% + 经营 20% + 舆情 10%；`≥60` 高 / `≥30` 中 / 其余低；
- 关键词用**原文包含**匹配，不用分词结果（`资金链断裂`、`立案调查` 会被 jieba 切碎）；
- `app.run(host="0.0.0.0")`：容器内 127.0.0.1 是容器自己，宿主机必须走 0.0.0.0；
- 启动时 `jieba.initialize()` 预热，避免首次调用等待。

### 2. Django 侧（`risk_app/nlp_infer.py`）

| 关注点 | 做法 |
| --- | --- |
| 超时 | `urlopen(..., timeout=5)`，不让请求线程挂住 |
| 降级 | 连接失败/返回异常/格式不对，统一返回 `ok=False` + 可操作提示，页面不报 500 |
| 转换 | 服务端 `details` → 页面扁平结构（四维分数、分类关键词、高亮文本、摘要） |
| 安全 | 高亮前先 `html.escape` 全文，再包 `<b>`；防 XSS |
| 高亮 | 在原文上定位区间、长词优先、不重叠，避免 `行政<b>处罚</b>` 嵌套 |
| 配置 | `NLP_SERVICE_URL` 支持环境变量，容器编排时指向 `http://nlp:5000` |

### 3. 前端（`risk_app/templates/model_show.html`）

左侧文本框（预填 159 字演示文本）+「开始识别」；右侧大字综合分、等级徽标、四维卡片、
分类关键词彩色标签、高亮文本与摘要；顶部显示服务地址与在线/离线徽标；
服务离线时页面顶部直接给出启动命令，提交后结果区显示同样的提示。

## 四、实测数据（可复核）

| 场景 | 输入 | 结果 |
| --- | --- | --- |
| 指导书示例文本 | 「该公司涉嫌财务造假，已被证监会立案调查，并处罚款」 | 命中 5 词，合规 37 / 财务 10，综合 **17.8，低风险**，14 词 |
| 页面演示文本 | 159 字，覆盖四类 29 个词 | 合规 92 / 财务 74 / 经营 37 / 舆情 51，综合 **71.5，高风险** |
| 空文本 | 空格 | `{"error":"文本为空"}` |
| GET 调 /analyze | — | 405（只接受 POST） |

> **注意一处出入**：指导书步骤 2 的注释里写该示例返回 `63.0 high`，但按它自己的规则
> （每类封顶 100、加权 40/30/20/10）这段文本只命中 5 个词，算出来是 17.8（低）。
> 我按**规则**实现，不按注释里的数字凑；页面演示改用覆盖四类的高密度文本，得到 71.5 高风险。

## 五、部署说明（《本地模型部署说明》）

### 1. 环境要求

- Docker Desktop 4.20+，已启动；Windows 需开 WSL2 后端；
- 磁盘 ≥ 2GB（镜像约 200MB，基础镜像约 130MB）；
- 若拉取基础镜像超时，Dockerfile 已用华为云同步地址。

### 2. 构建与启动

```bat
cd nlp_service
docker build -t nlp-risk .                                  :: 构建镜像
docker run -d -p 5000:5000 --name nlp-risk ^
  --restart unless-stopped nlp-risk                          :: 运行容器
docker ps --filter name=nlp-risk                             :: 查看状态
docker logs --tail 20 nlp-risk                               :: 看启动日志
curl http://localhost:5000/health                            :: 健康检查
```

一条命令版：`nlp_service\build_and_run.bat`（含构建、清旧容器、等待健康检查）。

Django 与 NLP 一起起（可选）：项目根目录 `docker compose up -d`，此时 Django 通过
`http://nlp:5000` 访问服务（`docker-compose.yml` 已注入 `NLP_SERVICE_URL`）。

### 3. 端口说明

| 端口 | 用途 | 说明 |
| --- | --- | --- |
| 5000 | NLP 微服务 | 容器 5000 → 宿主 5000；只在本机监听 |
| 8021 | Django 主站 | 页面 `/model/show/`，接口 `/model/analyze/` |
| 3307 | MySQL | 独立实例，不打进镜像 |

### 4. 故障排查（对应表 15-9）

见 `nlp_service/README.md` 第四节，逐条对应「现象—原因—处理」，含本机实测的一个特例：
**Windows 上重复绑定 0.0.0.0:5000 不会报端口冲突**（`SO_REUSEADDR`），不能靠启动日志判断，
要用 `netstat -ano | findstr :5000` 或 `docker ps` 确认。

## 六、部署验证与故障演练（表 15-7，最终结果见第十一节）

| 编号 | 操作 | 预期 | 实测结果 |
| --- | --- | --- | --- |
| V-01 | `docker ps` 查看容器 | Up，`0.0.0.0:5000->5000/tcp` | ⏳ 未执行：本机未装 Docker |
| V-02 | `curl /health` | `status: ok` | ✅ `{"service":"nlp-risk-analyzer","status":"ok"}`（宿主机同端口） |
| V-03 | 页面提交演示文本 | 综合分、四维、关键词、高亮 | ✅ 71.5 高风险，29 词，四维 74/37/92/51 |
| V-04 | 停服务后提交 | 提示“NLP 服务未启动”，不报 500 | ✅ 页面 200，`code=1`，提示含启动命令 |
| V-05 | 重启服务后再提交 | 恢复正常 | ✅ `/health` 200，分析 `code=0`（15.0 低风险） |
| V-06 | 改词库后 rebuild + run | 新词库生效 | ⏳ 未执行（需 Docker） |
| V-07 | 端口被占用时启动 | 启动失败并提示冲突 | ⚠️ 部分：宿主机二次绑定未报错（Windows `SO_REUSEADDR`），容器层未执行 |
| V-08 | 删镜像后启动容器 | 提示镜像不存在 | ⏳ 未执行（需 Docker） |

**（历史记录）当时未跑容器层的原因**：

1. `docker` 命令不存在，Docker Desktop 未安装；
2. `wsl -l -v` 无任何发行版，WSL2 未安装；
3. 当前会话**没有管理员权限**（`net session` 被拒），而安装 Docker Desktop 与启用
   WSL2/虚拟化都需要管理员并重启。

安装过程与踩坑（CDN 只有 50 KB/s、GitHub 不可达、WSL 商店包 4 小时）记录在 **`安装DockerDesktop.md`**。
最终用「16 线程分块 + 代理」把 350 MB 的 WSL 3.0.5 安装包压到 90 秒，随后 build 成功、八项验证全绿。

## 七、技术选型对比（≥200 字）

云端大模型与本地轻量模型不是替代关系，本项目两条链路都保留。云端（项目 14）通过 API 直接
生成分数、四维分析与建议，能力上限高，能输出成段文字，适合人工辅助决策；代价是依赖公网与
Key、按 Token 计费、企业描述要上传第三方。本地轻量模型（本项目）只用词库加规则，能力粗糙，
但胜在三条：一是不出网，文本留在本机，符合企业对敏感经营数据的基本要求；二是零调用成本，
可以拿来批量初筛上万条记录；三是几十毫秒返回，适合放在列表页做实时标记。两者组合的合理分工是
「本地先筛、云端再判」：本地把明显命中的记录挑出来并给出高亮依据，云端只对少量高风险样本做
深度解读，这样既有可解释的低成本兜底，又保留了大模型的表达与分析能力。本次实测也印证了取舍：
本地服务对「处罚/立案调查/失信」这类特征词非常敏感，但对「注册资本骤降」「关联交易异常」这类
需要上下文推理的风险无能为力；云端模型则相反。因此系统里把本地模型定位为**初筛与解释工具**，
最终风险分仍以 12 项结构化指标的规则评分为准，避免用关键词命中直接替代业务判断。

## 八、文件清单

| 文件 | 说明 |
| --- | --- |
| `nlp_service/app.py` | 微服务本体（词库、评分、路由、预热） |
| `nlp_service/Dockerfile` | 镜像定义（华为云基础镜像、清华源、HEALTHCHECK） |
| `nlp_service/requirements.txt` | flask 3.0.0 / jieba 0.42.1 |
| `nlp_service/run_local.bat` | 宿主机直跑 |
| `nlp_service/build_and_run.bat` | 构建 + 运行 + 健康检查 |
| `nlp_service/docker_env_check.bat` | 环境自检（docker/WSL/端口/镜像/健康检查） |
| `nlp_service/README.md` | 接口契约、评分规则、运行方式、常见问题 |
| `risk_app/nlp_infer.py` | Django 调用封装（超时、降级、转换、高亮转义） |
| `risk_app/templates/model_show.html` | 前端展示页 |
| `risk_app/views.py` | `model_show()` / `model_analyze()` |
| `docker-compose.yml` | Django + NLP 编排（可选） |
| `Dockerfile.web` | Django 主站镜像（可选） |
| `code/` | 上述 5 个核心文件的副本，便于提交 |
| `截图/01` | 页面识别结果（71.5 高风险、29 词、高亮） |
| `截图/02` | 服务停止时的降级提示 |
| `截图/03` | 本地启动日志 + curl 健康检查/分析/405（真实输出） |

## 九、测试

新增 `LocalModelTests` 7 个用例，覆盖：页面渲染、未登录跳转、服务不可用降级、空文本、
结果转换与高亮、HTML 转义（XSS）、标签不嵌套。`manage.py test risk_app` 共 **80 个全过**。

## 十、下一步

1. 词库外置成 JSON 并挂 volume，改词不用 rebuild（现在要 rebuild，虽然层缓存后只要 2 秒）；
2. 给 `/analyze` 加限流（同一 IP 每分钟 N 次），页面被刷时不至于打满容器；
3. 用 `docker compose` 把 MySQL 也纳入编排，做真正的一键起全站（现在 compose 只管 web + nlp）；
4. 生产环境把 Flask 开发服务器换成 gunicorn/waitress，去掉那行 "development server" 警告。

---

## 十一、容器层最终结果（2026-11-23 补做，全部实测）

装好 Docker 后按表 15-7 逐项跑完，八条全部通过，截图见 `截图/04`、`截图/05`。

### 1. 环境实况

| 项 | 值 |
| --- | --- |
| Docker Desktop | 4.99.0（引擎 29.9.3，`docker info` 正常） |
| WSL | 3.0.5.0，内核 6.18.58.1-1（装法见 `安装DockerDesktop.md` 第七节） |
| 基础镜像 | 华为云同步的 `python:3.10-slim`（Docker Hub 直连超时，镜像源是必需的） |
| 镜像 | `nlp-risk:latest`，198 MB，ID `1cde466c1c32` |
| 容器 | `nlp-risk`，`Up (healthy)`，`0.0.0.0:5000->5000/tcp` |
| 构建耗时 | 首次 6 分 20 秒（其中 pip 装依赖 356 秒）；改代码后重建 0.0–2 秒（层缓存） |

### 2. 八条验证（表 15-7）

| 编号 | 操作 | 预期 | 实测结果 |
| --- | --- | --- | --- |
| V-01 | `docker ps` | Up，`0.0.0.0:5000->5000/tcp` | ✅ `Up (healthy)`，端口映射正确 |
| V-02 | `curl /health` | `status: ok` | ✅ `{"service":"nlp-risk-analyzer","status":"ok"}` |
| V-03 | 页面提交演示文本 | 分数 + 四维 + 关键词 + 高亮 | ✅ 71.5 高风险，29 词，74/37/92/51 |
| V-04 | `docker stop` 后提交 | 提示未启动，不报 500 | ✅ 容器 `Exited (137)`，页面 200 + `code=1` |
| V-05 | `docker start` 后再提交 | 恢复正常 | ✅ `Up (healthy)`，分析 `code=0` |
| V-06 | 改词库后 rebuild + run | 新词库生效 | ✅ 「处罚」9→3，合规分 9→3；恢复后回到 9 |
| V-07 | 端口被占用时启动 | 启动失败并提示冲突 | ✅ `Bind for 0.0.0.0:5000 failed: port is already allocated` |
| V-08 | 删镜像后启动容器 | 提示镜像不存在 | ✅ `Unable to find image 'nlp-risk:latest' locally` + 拉取超时 |

> V-06 的做法：`docker build`（层缓存，秒级）→ `docker rm -f` + `docker run` → `curl` 对同一段文本
> 「公司被处罚」取合规分，权重改前 9、改后 3、恢复后 9，三次都留了输出。
> V-08 删镜像后 `docker run` 会尝试从 Docker Hub 拉取 `nlp-risk`，本机网络下超时退出——正好同时印证了
> 「镜像不能在公共仓库找到」和「必须本地 build」两件事。

### 3. 与设计文档的对应

| 设计点 | 容器内实测 |
| --- | --- |
| Dockerfile 五层（FROM/WORKDIR/COPY/RUN/COPY+CMD） | 构建日志 `#4 [1/5]`～`#9 [5/5]` 一一对应 |
| `EXPOSE 5000` + `-p 5000:5000` | `docker ps` 显示 `0.0.0.0:5000->5000/tcp` |
| `HEALTHCHECK` | 状态列出现 `(healthy)`，日志里可见 Python 探活请求 |
| 依赖走清华源 | `#8 RUN pip install ... -i https://pypi.tuna.tsinghua.edu.cn/simple` |
| 服务绑 0.0.0.0 | 容器日志 `Running on all addresses (0.0.0.0)`、`http://172.17.0.2:5000` |