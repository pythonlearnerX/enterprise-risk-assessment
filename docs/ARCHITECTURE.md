# 架构与代码地图（ARCHITECTURE）

> 一页看懂：请求怎么走、数据表怎么连、每个文件管什么、改功能该动哪里。
> 更细的「功能 → 行号」见根目录 `docs/答辩材料/代码地图.md`。

---

## 一、分层

```
浏览器
  │  HTTP
  ▼
risk_project/urls.py        根路由：/admin/ 交给 Django Admin，其余交给 risk_app
  ▼
risk_app/urls.py            36 条路由（app_name = "risk_app"，模板里用 {% url 'risk_app:xxx' %}）
  ▼
risk_app/views.py           业务视图：取参数 → ORM 查询 → 组装 context → render / JsonResponse
  ├── decorators.py         @login_required（Django）+ @admin_required（本项目）
  ├── risk_calc.py          评分：12 项 → 四维 → 总分 → 等级
  ├── analytics.py          看板统计：基尼、洛伦兹、分位带、相关矩阵、卡方、z 分数、α/PC1
  ├── abtest.py             A/B 分桶（md5 确定性）+ 两比例 z 检验
  ├── ai_service.py         大模型调用（用户自带 Key，超时降级）
  ├── nlp_infer.py          调本地 Flask 微服务（5 秒超时 + 降级）
  ├── report_pdf.py         fpdf2 生成 A4 PDF
  └── charts.py             纯 Python SVG 备用图（无 JS 环境也能出图）
  ▼
risk_app/models.py          11 张表（业务表用 db_table 显式命名）
  ▼
MySQL 8.4
```

前端：`templates/`（24 个）+ `static/`（css / js / vendor / json）。
图表统一走「视图内嵌首屏数据 → 前端 ECharts 渲染 → 交互再调 `/api/chart/*`」。
Bootstrap 与 ECharts 都是**本地文件**，断网也能显示（答辩现场没网是常态）。

---

## 二、十一条路由分类

| 分组 | 路径 | 说明 |
| --- | --- | --- |
| 基础 | `/`、`/login/`、`/logout/`、`/health/` | `/health/` 不用登录，返回 MySQL 版本 + 表名，排错第一步 |
| 企业 | `/enterprise/list/`、`/enterprise/detail/<pk>/` | 列表含 8 条件组合查询 + 分页 + CSV |
| 风险 | `/risk/list/`、`/risk/detail/<pk>/` | 两种视图（四维汇总 / 12 项明细）+ CSV |
| 可视化 | `/chart/enterprise/`、`/chart/risk/`、`/chart/analysis/`、`/chart/map/`、`/chart/compare/` | 页面 + `/api/chart/*` 数据接口 |
| 报告 | `/enterprise/<pk>/report.pdf` | fpdf2 生成 |
| AI | `/settings/ai/`、`/api/ai/test/`、`/api/ai/analyze/`、`/api/ai/explain/`、`/manage/ai-insights/` | 用户级 Key |
| 大模型预估 | `/predict/`、`/predict/api/` | 项目 14 |
| 本地模型 | `/model/show/`、`/model/analyze/` | 项目 15，前端调微服务 |
| 实验 | `/ab/`、`/ab/<pk>/`、`/ab/<pk>/toggle/`、`/api/ab/event/` | A/B 后台 |
| 管理 | `/console/`、`/manage/users/`、`/alerts/` | 自建后台、用户管理、预警订阅 |
| 兜底 | `/login/<path:rest>` | 地址栏把说明文字粘进 URL 时重定向回登录页 |

---

## 三、数据表（11 张）

| 表 | 模型 | 关键字段 | 关系 |
| --- | --- | --- | --- |
| `enterprise` | `Enterprise` | `usc_code`、`firm_name`、`ope_status`(1在营/2注销/3吊销)、`reg_cap`、`district`(区划码) | 1 → N 风险 |
| `risk_indicator` | `RiskIndicator` | 12 项指标 `cai_*`/`s_an_*`/`li_an_*`/`zhi_*`、四维分、`total_risk_score`、`risk_level` | N → 1 企业 |
| `user_profile` | `UserProfile` | `role`(admin/normal)、`department`、`phone` | 1:1 `auth_user` |
| `audit_log` | `AuditLog` | `action`、`target`、`ip` | N → 1 用户 |
| `ai_setting` | `AISetting` | `provider`、`base_url`、`model_name`、`api_key` | 1:1 用户 |
| `risk_snapshot` | `RiskSnapshot` | `year`、`total_score`、`level`、`note`（模拟数据标记） | N → 1 企业 |
| `alert_rule` | `AlertRule` | `metric`、`threshold`、`level`、`enabled` | N → 1 用户 |
| `ab_experiment` | `ABExperiment` | `key`、`status`、`split` | 1 → N 分配 |
| `ab_assignment` | `ABAssignment` | `variant`(A/B)、`date` | N → 1 实验/用户 |
| `ab_event` | `ABEvent` | `kind`、`variant` | N → 1 实验/用户 |
| `ai_insight` | `AIInsight` | `scope`、`target`、`facts`、`answer`、`ok` | N → 1 用户 |

> 关键设计：`RiskIndicator.save()` 里强制 `recalculate()`，**分数与等级永远同步**（这是踩过坑之后加的）。

---

## 四、评分链路（最重要的一段）

```python
# risk_app/risk_calc.py
calc_risk(values, mode="count"|"points", year_weights=..., dim_weights={...0.25})
  ├── 每维 3 年指标 → 加权平均
  ├── mode="count" ：安全分 = 25 − 平均次数，风险分 = 25 − 安全分（扣分制）
  ├── mode="points"：输入本身是 0–25 风险点，直接取均值
  ├── 四维 → 总分为四维均值（0–100）
  └── risk_level(total)：≥80 高 / ≥60 中 / 其余低
```

**不要改公式与阈值**，除非用户明确要求：基尼、卡方、看板文案都基于这套分数。

---

## 五、统计模块（analytics.py）

| 函数 | 产出 | 答辩怎么说 |
| --- | --- | --- |
| `_quantile` | P25/P50/P75/P90（线性插值，同 numpy） | 同规模正常区间 |
| `_pearson` / `_spearman` | 相关矩阵、秩相关 | 四维是否同向 |
| `_pc1` | 第一主成分特征值与载荷（幂迭代） | 一维能概括多少信息 |
| `_redundancy` | α、PC1、Top10% 重合、等级改判率 | **能不能用一维替代四维** |
| `_chi2_sf` | 卡方上尾概率（df 偶数闭式解，不依赖 scipy） | 状态与等级是否独立 |
| `build()` | 上面全部 + 7 条自动结论 | 看板数据源 |

口径细节与答辩话术：`docs/STATISTICS.md`。

---

## 六、常见改动指南

| 需求 | 改哪里 | 注意 |
| --- | --- | --- |
| 加一个筛选条件 | `views.enterprise_list` 取参数 → `views.py` 的 `qs = qs.filter(...)` → 模板表单 → `qs_suffix` 拼进分页 | 别忘了 `qs_suffix`，否则翻页丢条件 |
| 加一个页面 | `urls.py` 加路由 → `views.py` 加视图 → `templates/` 加模板 → `base.html` 加菜单 | 菜单显隐只控制显示，权限要在视图拦 |
| 改图表 | `templates/` 里的 ECharts 配置 + `views.chart_data_*` 接口 | 接口不加 `@cache_page` |
| 加一个测试 | `risk_app/tests.py`，继承 `BaseData`（已建好用户与样例企业） | 见 `docs/TESTING.md` |
| 换数据库 | 只改 `.env` | `settings.py` 已读环境变量 |
| 加统计指标 | `analytics.py` 的 `build()` 加字段 → 模板卡片 → 同步 `docs/STATISTICS.md` | 数字必须能复算 |