# AGENTS.md — 给接手本项目的 AI 的操作规约

> 你是被请来接手的 AI。这份文件的作用：让你在 10 分钟内知道「这是什么、怎么跑、改哪里、不能碰什么、怎么算改完」。
> **请先读完本文件再动手，不要在没跑通测试前修改业务代码。**

---

## 0. 三十秒上下文

- 项目：企业风险评估系统（Django 6.1 + MySQL 8.4），学生课程实训交付物。
- 数据：企业 10000 条、风险记录 10000 条（课程提供的一期快照，`dataset/*.csv`）。
- 现状：六大模块跑通；`manage.py test risk_app` **80 条全绿**；Docker 微服务（项目 15）已构建运行过。
- 文档：`docs/` 下有架构、跑通、测试、统计、报告五份说明；`课次/` 下是 17 个课次的交付文档。

---

## 1. 硬性规则（违反会导致返工）

1. **不要改 `risk_calc.py` 的评分公式与 60/80 阈值**，除非用户明确要求。分数是报告与答辩的核心，改公式会让所有既有结论（基尼、卡方、看板数字）失效。
2. **不要在视图里写裸 SQL**：本项目统一走 ORM；只有 `/health/` 与 EXPLAIN 类诊断才用 `connection.cursor()`。
3. **不要给数据接口加 `@cache_page`**：曾经加过 60 秒缓存，导致「改完分数图表不更新」，排查了很久（见 `docs/RUNBOOK.md` 的坑 2）。
4. **不要用 `request.GET.get("ids")` 取多选参数**：必须 `getlist`（坑 5）。
5. **权限必须拦在后端**：模板里 `{% if %}` 只控制显隐，视图要加 `@login_required` / `@admin_required`。
6. **模拟数据必须标注**：任何造出来的数据都要在字段 `note` 或页面徽标里写明「模拟」，参见 `seed_demo_history.py`。
7. **不要把密码/Key 写进代码**：连接参数走 `.env`（`settings.py` 已实现零依赖加载）。
8. **改完必须跑**：`python manage.py test risk_app`（80 条）+ `python manage.py check`，两条都要绿。

---

## 2. 环境与命令（Windows 为主）

```bash
# 一次性
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
copy .env.example .env          # 然后填数据库账号
python manage.py migrate
python data_import.py           # 或 --sample 只导 100 行

# 每天
python manage.py runserver 127.0.0.1:8021
python manage.py test risk_app
python manage.py check
```

排错顺序（重要）：`/health/` 能否返回 JSON → 数据库通不通 → `.env` 读没读到 → 迁移是否执行。

---

## 3. 代码地图（改功能先看这张表）

| 你要改的东西 | 文件 | 入口 |
| --- | --- | --- |
| 页面长什么样 | `risk_app/templates/*.html` | 24 个模板，`base.html` 是骨架 |
| 页面取什么数据 | `risk_app/views.py` | 36 条路由，见 `risk_app/urls.py` |
| 数据表结构 | `risk_app/models.py` | 11 张表，业务表用 `db_table` 显式命名 |
| 评分规则 | `risk_app/risk_calc.py` | `calc_risk()`，两种口径 count/points |
| 看板统计 | `risk_app/analytics.py` | `build()` 返回所有卡片数据 |
| 权限 | `risk_app/decorators.py` | `admin_required` |
| PDF | `risk_app/report_pdf.py` | fpdf2，注册 simhei |
| 大模型 | `risk_app/ai_service.py` / `llm_predict.py` | 用户级 Key，超时降级 |
| NLP 微服务 | `nlp_service/app.py` + `Dockerfile` | Flask + jieba，端口 5000 |
| 测试 | `risk_app/tests.py` | 19 个类 / 80 条，按模块分组 |

更细的「功能 → 文件 → 行号」见根目录 `00-代码地图.md`。

---

## 4. 判断「改对了」的标准

- `manage.py test risk_app` → `Ran 80 tests ... OK`
- `manage.py check` → `System check identified no issues`
- 手动看三页：首页（`/`）、企业列表（`/enterprise/list/`）、风险详情（`/risk/detail/<id>/`），不报 500。
- 若动了统计：数字必须能从数据库复算（脚本见 `scripts/`，别硬编码）。

---

## 5. 这个项目里已经踩过的坑（别重踩）

| # | 坑 | 正确做法 |
| --- | --- | --- |
| 1 | 改分数没改等级，出现「88.67 分 / 中风险」 | `RiskIndicator.save()` 里统一调 `recalculate()` |
| 2 | 图表接口加了 `cache_page(60)`，改数据不刷新 | 数据接口不加页面缓存 |
| 3 | `json_script` 二次编码 → 图表空白 | 视图传 Python 对象，不要先 `json.dumps` |
| 4 | 热力图 `visualMap` 缺 `dimension` → 整片灰 | 显式指定数值所在的维度 |
| 5 | 复选 `?ids=1&ids=2` 用 `get()` 只拿到一个 | `request.GET.getlist("ids")` |
| 6 | 服务端导出 PDF（Edge 无头 / Word COM）失败 | 用 fpdf2 纯 Python 绘制 |
| 7 | 企业详情「经营状态」显示裸码 1/2/3 | 模板里映射成 在营/注销/吊销 |
| 8 | 未登录访问 `/alerts/` 500 | 视图补 `@login_required` |

完整 27 条见 `课次/项目16-系统测试报告/` 与 `docs/RUNBOOK.md`。

---

## 6. 你不应该做的事

- 不要为了「跑起来」删测试或跳过断言；
- 不要把 `dataset/` 的全量 CSV 提交进 git（.gitignore 已排除，只留 100 行样本）；
- 不要把 `_tmp/`、`.venv/`、`课次/**/截图/` 提交（体积大且可再生成）；
- 不要在没看 `docs/STATISTICS.md` 的情况下改看板结论文案——数字和文案是绑定的。

---

## 7. 如果用户让你「写实训报告 / 改答辩 PPT」

- 报告与 PPT 的既有事实（数字、结论、局限）都在 `docs/REPORT-GUIDE.md` 与 `00-答辩知识包.md`，**先读再写**，不要重新编数字；
- 报告要求「7 章 + 2 附录」的结构见 `课次/项目16-系统测试报告/README.md`；
- 答辩 PPT 的图表取舍理由见 `课次/项目17-答辩PPT/README.md`（每张图都要能回答「这张图证明什么」）。