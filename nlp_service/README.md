# nlp_service —— 本地风险文本识别微服务（项目 15）

Flask + jieba 的轻量 NLP 服务，独立于 Django 运行，容器的 5000 端口映射到宿主机 5000。

## 一、接口契约（表 15-2）

| 接口 | 方法 | 请求 | 返回 |
| --- | --- | --- | --- |
| `/health` | GET | 无 | `{"status":"ok","service":"nlp-risk-analyzer"}` |
| `/analyze` | POST | `{"text":"待分析文本"}` | `{"total_score":71.5,"risk_level":"high","details":{...},"keywords_found":29,"word_count":159}` |
| 错误 | — | 文本为空 | `{"error":"文本为空"}` |

`details` 里四类各含 `score` / `keywords` / `count` / `label`（财务、经营、合规、舆情）。

## 二、评分规则（表 15-3）

| 类别 | 权重 | 示例词（权重） |
| --- | --- | --- |
| 合规 | 40% | 立案调查(10)、证监会(10)、失信(10)、处罚(9)、诉讼(8) |
| 财务 | 30% | 资金链断裂(10)、资不抵债(10)、亏损(10)、坏账(8) |
| 经营 | 20% | 倒闭(10)、破产(10)、停产(9)、裁员(9) |
| 舆情 | 10% | 安全事故(10)、丑闻(10)、曝光(8)、投诉(7) |

- 每类得分 = 命中词权重累加，**封顶 100**；
- 综合分 = 四类得分加权和；`≥60` 高、`≥30` 中、其余低。

> 关键词用「原文包含」匹配，不用分词结果：`资金链断裂`、`立案调查` 这类多字词会被 jieba 切碎，用分词比对会漏。jieba 只用于统计词数与预热。

## 三、三种运行方式

```bat
:: ① 本地直跑（不装 Docker，用于先验证代码）
run_local.bat                       => http://127.0.0.1:5000/health

:: ② 容器：构建 → 运行 → 健康检查
build_and_run.bat
:: 等价于
docker build -t nlp-risk .
docker run -d -p 5000:5000 --name nlp-risk --restart unless-stopped nlp-risk

:: ③ 与 Django 一起编排（在项目根目录）
docker compose up -d
```

## 四、常见问题（表 15-9）

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 拉基础镜像超时 | Docker Hub 受限 | Dockerfile 已用华为云同步的 `python:3.10-slim` |
| 容器启动后立即退出 | 启动报错或端口占用 | `docker logs nlp-risk`，再查 `netstat -ano | findstr :5000` |
| 宿主机访问 5000 失败 | 服务绑了 127.0.0.1 | 必须是 `app.run(host="0.0.0.0")`（已改） |
| 端口被占 | 旧容器或其它程序 | `docker ps -a` 清旧容器，或改用 `-p 5001:5000` |
| 中文乱码 | Content-Type 缺 charset | 请求头带 `application/json; charset=utf-8` |
| pip 安装慢 | 默认源 | 已用清华源 |
| 改代码不生效 | 还在跑旧镜像 | 重新 `docker build`，删旧容器再 run |
| 首次调用很慢 | jieba 加载词典 | 启动时 `jieba.initialize()` 预热（已做） |
| Windows 上二次启动不报端口冲突 | Windows 的 `SO_REUSEADDR` 允许重复绑定 0.0.0.0 | 改用 `docker ps`/`netstat` 判断，不要只看启动日志 |

## 五、文件

| 文件 | 作用 |
| --- | --- |
| `app.py` | 服务本体（词库、评分、路由） |
| `requirements.txt` | flask 3.0.0 / jieba 0.42.1 |
| `Dockerfile` | 基础镜像、依赖、端口、健康检查、启动命令 |
| `run_local.bat` | 宿主机直跑（自动补依赖） |
| `build_and_run.bat` | 构建 + 运行 + 等待健康检查 |