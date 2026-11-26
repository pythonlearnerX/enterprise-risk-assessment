# 企业风险评估系统 · 代码仓库说明

> 课程：模型开发综合实训（20262011）　学生：薛瑞 249990736 / 24 智科 4 班　指导教师：王恒达
> 技术栈：Django 6.1 + MySQL 8.4 + PyMySQL｜前端 Bootstrap 5.3 + ECharts 5.4（**本地文件，不依赖 CDN**）
> 数据规模：**企业 10000 条 / 风险记录 10000 条**（课程提供的一期快照）
> 状态：六大模块全部跑通，自动化用例 **80 条全绿**，容器化与答辩材料齐备

---

> 答辩时先开 **`00-答辩导航.md`**：24 个常见问题 → 文件:行号，找代码比翻目录快。

## 一、这是什么

一套「企业风险查询 + 评分 + 可视化 + 报告导出」的 Django Web 系统，覆盖课程实训的 6 个模块：

| 模块 | 能力 | 对应课次 |
| --- | --- | --- |
| 企业数据管理 | 列表、8 条件组合查询、分页、详情、CSV 导出 | 项目 04 / 07 / 08 |
| 数据可视化 | 企业 6 图 + 风险 3 图 + 图表 JSON 接口 | 项目 10 / 11 |
| 风险计算与报告 | 12 项指标 → 四维 → 总分 → 等级；A4 PDF 报告 | 项目 12 |
| 用户权限管理 | 登录、会话、角色分流、自定义后台、审计日志 | 项目 06 / 09 / 13 |
| AI 风险预估 | 用户自带 Key 调大模型，**只解释、不参与打分** | 项目 14 |
| 模型部署展示 | Flask + jieba 微服务，Docker 容器化 | 项目 15 |

此外还有三类**加分项**（分析看板 8 视角、重庆区县地图、A/B 实验、AI 解读闭环），
与系统测试报告、答辩 PPT 一起放在 `课次/`。

---

## 二、5 分钟跑通（照抄即可）

### 0. 前置

| 依赖 | 版本 | 说明 |
| --- | --- | --- |
| Python | 3.12（3.10+ 均可） | 建议建虚拟环境 |
| MySQL | 8.0 / 8.4 | 本项目开发时用便携版，端口 **3307**；你自己的 MySQL 默认 3306 也行 |

### 1. 装依赖

```bash
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2. 配置数据库连接（**不要改代码**）

```bash
copy .env.example .env            # macOS/Linux: cp .env.example .env
# 编辑 .env，填你自己的数据库账号密码与端口
```

`risk_project/settings.py` 会自动读取根目录 `.env`（零依赖实现，见文件顶部 `_load_dotenv`）。
`.env` 已在 `.gitignore` 里，不会被提交。

### 3. 建库 + 建表

```sql
CREATE DATABASE risk_assessment DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
```

```bash
python manage.py migrate
python manage.py createsuperuser
```

### 4. 导入数据

```bash
python data_import.py
```

只导 100 行样本快速验证：

```bash
python data_import.py --sample
```

### 5. 起服务

```bash
python manage.py runserver 127.0.0.1:8021
```

### 6. 验收（这三条都能过，说明环境没问题）

```bash
curl http://127.0.0.1:8021/health/          # 期望 {"ok": true, "mysql": "8.4.x", "tables": [...]}
python manage.py test risk_app              # 期望 Ran 80 tests ... OK
python manage.py check                      # 期望 System check identified no issues
```

> `/health/` 不用登录，是专门给排错用的：能返回数据库版本和表名列表，说明 Django ↔ MySQL 通了。

---

## 三、目录地图

```
risk_project_xuerui/
├── manage.py                     Django 入口
├── requirements.txt              依赖（Django / PyMySQL / fpdf2 / pandas）
├── .env.example                 数据库连接模板（复制成 .env）
├── data_import.py               CSV → MySQL 导入（全量 / --sample）
├── dataset_process.py           原始 CSV 清洗
├── AGENTS.md                    ★ 给「接手的 AI」的操作规约，先读这个
│
├── risk_project/                工程配置
│   ├── settings.py              .env 加载、数据库、静态文件、登录跳转
│   ├── urls.py                  根路由（/admin/ + risk_app）
│   └── wsgi.py / asgi.py
│
├── risk_app/                    唯一业务应用
│   ├── models.py                11 张表：企业、风险、用户角色、审计、AI 配置、
│   │                            快照、预警、A/B 三件套、AI 解读记录
│   ├── views.py                 业务视图（约 1260 行，36 条路由）
│   ├── urls.py                  应用路由
│   ├── risk_calc.py             评分：count（扣分制）/ points（风险点）两套口径
│   ├── analytics.py             分析看板 8 视角（基尼、洛伦兹、分位带、相关矩阵、
│   │                            卡方残差、z 分数、cohort、冗余度 α/PC1）
│   ├── abtest.py                A/B 分桶（md5 确定性）+ 两比例 z 检验
│   ├── ai_service.py            OpenAI 兼容客户端（用户自带 Key）
│   ├── nlp_infer.py             调本地 NLP 微服务（超时 5s + 降级）
│   ├── llm_predict.py           大模型风险预估（项目 14）
│   ├── report_pdf.py            fpdf2 生成 A4 PDF（注册 simhei 中文字体）
│   ├── charts.py                纯 Python SVG 备用图（无 JS 也能出图）
│   ├── decorators.py            admin_required：未登录→登录页，已登录无权限→403
│   ├── auth_views.py            登录 / 退出 / 记住我
│   ├── tests.py                 80 条用例，19 个测试类
│   ├── templates/               24 个页面模板（深色主题）
│   ├── static/                  css / js / vendor / json（重庆 GeoJSON）
│   └── management/commands/     score_preview、seed_demo_history、ab_seed、ab_simulate
│
├── nlp_service/                 项目 15：Flask + jieba 微服务 + Dockerfile
├── scripts/                     环境检查、导入辅助、验证脚本
├── docs/                        ★ 接手必读
│   ├── 答辩材料/                代码地图（功能→行号）、答辩知识包、答辩速查卡、整理说明
│   ├── 交接包/                  换 AI 用的单文件上下文 + 压缩包
│   ├── ARCHITECTURE.md          架构与数据字典
│   ├── STATISTICS.md            全部统计口径与实测值
│   ├── RUNBOOK.md               从零跑通与排错
│   ├── TESTING.md               测试说明
│   └── REPORT-GUIDE.md 等       报告骨架、PPT 复盘、提示词包
├── 课次/                        课次文档（项目 01–18，每项一个 README + 截图）
└── 00-答辩导航.md                ★ 答辩时先开这个：问题 → 文件:行号
```

---

## 四、关键事实（写报告时直接引用，全部实测）

| 项 | 数值 | 来源 |
| --- | --- | --- |
| 数据量 | 企业 10000 / 风险 10000 / 快照 24 | MySQL 实查 |
| 风险分档 | 低 7500（75.0%）/ 中 2266（22.7%）/ 高 234（2.34%） | 阈值 60 / 80 |
| 全库均分 | 35.17（最低 4.67，最高 88.67） | SQL 聚合 |
| 基尼系数 | 0.3936（前 10% 企业贡献 22.31% 风险分） | analytics.build() |
| 四维相关 | 0.949–0.956（平均 r̄=0.9524） | analytics._redundancy() |
| Cronbach α / PC1 | 0.9877 / 96.43%，PC1 权重 25.0/25.1/25.0/24.9 | 同上（等权即主成分权重） |
| 卡方 | χ²=1.72、df=4、p=0.787（状态与等级无关） | 同上 |
| 自动化用例 | 80 条 / 约 12 秒 / 全绿 | `manage.py test` |
| 页面响应 | 72–412 ms（中位数，11 个页面） | 2026-11-24 实测 |
| N+1 优化 | 23 条 SQL → 1 条（select_related） | 同上 |
| 容器 | `nlp-risk:latest` 198 MB，`Up (healthy)`，端口 5000 | docker ps |

---

## 五、文档索引（按「接手者」的需要排序）

| 想做什么 | 先读 |
| --- | --- |
| **让 AI 接手改造** | `AGENTS.md` → `docs/AI-HANDOFF.md` |
| 跑起来 / 排错 | 本文件第二节 → `docs/RUNBOOK.md` |
| 看懂代码分层 | `docs/ARCHITECTURE.md` → `docs/答辩材料/代码地图.md` |
| 加/改用例 | `docs/TESTING.md` |
| 讲清统计口径 | `docs/STATISTICS.md` → `统计学变量说明-答辩版.docx` |
| 写实训报告 | `docs/REPORT-GUIDE.md` → `课次/课程总览.md` |
| 答辩 | `docs/答辩材料/答辩速查卡.md` → `课次/项目17-答辩PPT/README.md` |
| 交给其他 AI / 要提示词 | `docs/AI-PROMPTS.md`（评审·改 PPT·写报告三条提示词 + 纠偏话术） |
| 改 PPT / 评估可用性 | `docs/PPT-REVIEW.md`（AI 腔诊断 + 两条叙事线 + 非专业用户可用性七条改进） |
| 各课次交付物 | `课次/项目NN-*/README.md` |

---

## 六、已知限制（写报告要如实交代）

1. **数据只有一期快照**：`风险详情` 页的「近年评分」是 `seed_demo_history` 生成的**模拟值**（0.90/0.95/1.00 等比缩放），页面有徽标、图下有说明，不参与任何统计与结论；
2. **企业类型码未映射**：`firm_type` 存的是源数据代码（1100/1151…），课程未给字典；
3. **AI Key 明文入库**：课程环境可接受，生产需加密或接 KMS；
4. **PDF 用 fpdf2 手绘**：不依赖 Office/浏览器，但版式是固定模板，不是 HTML 渲染；
5. **开发服务器并发有限**：50 并发错误率约 18–22%（`runserver` 监听队列饱和），生产需换 gunicorn/waitress；
6. **四维高度共线**（α=0.988）：不可当成四个独立风险源解读，报告「方法局限」已写明。

---

## 七、许可与出处

课程实训项目，代码与文档由本人编写；数据集由课程方提供，仅用于课程作业，**不要再分发给第三方**。
截图与离线 HTML 因体积较大未入库，位置见 `docs/ASSETS.md`。