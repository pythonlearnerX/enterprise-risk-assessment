# 跑通与排错（RUNBOOK）

> 目标：换一台电脑 / 换一个 AI，能按这份文件从零跑起来；出错时按「症状 → 原因 → 处理」查。

---

## 一、从零跑通（Windows 为主，Mac/Linux 命令见括号）

### 1. 环境检查

```bash
python --version                 # 3.10+，推荐 3.12
mysql --version                  # 8.0 / 8.4
```

没有 MySQL？两条路：
- 装官方安装包（简单）；
- 用便携版（本项目开发时用的方式：解压 zip，`mysqld --no-defaults --basedir=... --datadir=... --port=3307`）。

### 2. 依赖

```bash
python -m venv .venv
.venv\Scripts\activate                    # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

> 卡在 `Installing build dependencies`：先 `pip install setuptools wheel`，再 `pip install --no-build-isolation 包名`。

### 3. 数据库

```sql
CREATE DATABASE risk_assessment DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
CREATE USER 'risk_user'@'localhost' IDENTIFIED BY '你的密码';
GRANT ALL PRIVILEGES ON risk_assessment.* TO 'risk_user'@'localhost';
FLUSH PRIVILEGES;
```

```bash
copy .env.example .env          # macOS/Linux: cp .env.example .env
```

`.env` 内容：

```ini
DB_NAME=risk_assessment
DB_USER=risk_user
DB_PASSWORD=你的密码
DB_HOST=127.0.0.1
DB_PORT=3307          # 你的 MySQL 是默认端口就写 3306
DJANGO_SECRET_KEY=dev-only-local
DJANGO_DEBUG=1
```

`settings.py` 顶部有零依赖的 `_load_dotenv()`，会自动读这个文件——**不用改任何代码**。

### 4. 建表 + 建账号 + 导数据

```bash
python manage.py migrate
python manage.py createsuperuser
python data_import.py --sample      # 先 100 行验证
python data_import.py               # 再全量 10000 行（约 40–60 秒）
```

### 5. 起服务

```bash
python manage.py runserver 127.0.0.1:8021
```

打开 <http://127.0.0.1:8021/login/>，用刚建的超级管理员登录。

### 6. 三条验收命令

```bash
curl http://127.0.0.1:8021/health/     # {"ok": true, "mysql": "8.4.x", "tables": [...]}
python manage.py test risk_app         # Ran 80 tests ... OK
python manage.py check                 # System check identified no issues
```

### 7. 可选：NLP 微服务（项目 15）

```bash
cd nlp_service
pip install flask==3.0.0 jieba==0.42.1
python app.py                          # 或 docker build -t nlp-risk . && docker run -d -p 5000:5000 nlp-risk
curl http://127.0.0.1:5000/health
```

Django 侧通过 `NLP_SERVICE_URL`（默认 `http://127.0.0.1:5000`）访问；服务没起时，页面会降级提示而不是报错。

---

## 二、排错表（按出现频率排序）

| 症状 | 原因 | 处理 |
| --- | --- | --- |
| `(2003, "Can't connect to MySQL server")` | MySQL 没起 / 端口不对 | 先确认 MySQL 在跑；核对 `.env` 的 `DB_PORT` |
| `(1045, "Access denied")` | 账号密码错 | `mysql -u risk_user -p` 手动连一次 |
| `(1049, "Unknown database")` | 没建库 | 执行第一节第 3 步的 `CREATE DATABASE` |
| `Table 'risk_assessment.enterprise' doesn't exist` | 没迁移 | `python manage.py migrate` |
| `No module named 'MySQLdb'` | 少了 PyMySQL 注册 | `risk_project/__init__.py` 应有 `pymysql.install_as_MySQLdb()` |
| `TemplateDoesNotExist: xxx.html` | 模板名写错 / 没建 | 对照 `views.py` 的 `render(request, "xxx.html", ...)` |
| 页面出来了但图空白 | 静态库没加载 / 数据是 `fetch` 拿的 | F12 看 Network：`echarts.min.js` 是否 200；接口是否 500 |
| 中文变方块（PDF） | 没注册中文字体 | `report_pdf.py` 里 `pdf.add_font("SimHei", "", "C:/Windows/Fonts/simhei.ttf")` |
| 下载文件名乱码 | Content-Disposition 未编码 | 用 RFC 5987：`filename*=utf-8''<quote(name)>` |
| 端口冲突 | 8021 被占 | `netstat -ano \| findstr :8021`，或换端口 |
| 50 并发大面积 `WinError 10061` | `runserver` 监听队列饱和 | 属开发服务器限制，生产换 gunicorn/waitress（遗留 L-03） |

---

## 三、八个「曾经踩过、别重踩」的坑

1. **改分数没改等级** → 页面出现「88.67 分 / 中风险」。修法：`RiskIndicator.save()` 里统一 `recalculate()`。
2. **数据接口加了 `@cache_page(60)`** → 改完数据图表一分钟才变。修法：数据接口不加页面缓存。
3. **`json_script` 二次编码** → 图表数字是字符串，图空白。修法：视图传 Python 对象，别先 `json.dumps`。
4. **热力图 `visualMap` 缺 `dimension`** → 整片一色。修法：显式指定数值所在维度。
5. **多值参数用 `get()`** → 勾选 3 家只对比 1 家。修法：`request.GET.getlist("ids")`。
6. **服务端导出 PDF 两条路都失败** → Edge 无头打印报 `Missing headless user data directory`；Word COM 报未注册。修法：fpdf2 纯 Python 绘制。
7. **企业详情经营状态显示裸码 `1`** → 模板没映射。修法：模板里 `{% if ope_status == '1' %}在营{% elif ... %}`。
8. **未登录访问 `/alerts/` 500** → 视图漏了 `@login_required`。修法：补装饰器（这条是测试报告里的 D-08）。

---

## 四、日常维护

```bash
# 每天开工
python manage.py runserver 127.0.0.1:8021

# 改完代码
python manage.py test risk_app && python manage.py check

# 重建演示快照（近年评分，模拟数据）
python manage.py seed_demo_history --top 8

# 清空演示快照
python manage.py shell -c "from risk_app.models import RiskSnapshot; RiskSnapshot.objects.all().delete()"

# 看某企业分数为什么是这个
python manage.py score_preview --risk-id 219
```

---

## 五、备份与重置

```bash
# 数据备份（结构 + 数据）
mysqldump -u risk_user -p risk_assessment > backup.sql

# 恢复
mysql -u risk_user -p risk_assessment < backup.sql

# 代码回滚（如果用 git）
git log --oneline -5
git checkout <commit> -- risk_app/
```