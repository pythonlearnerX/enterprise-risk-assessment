# 项目 04-企业数据管理（建工程 / 模型 / 迁移）

> 课程总览里项目 04 的主题是“企业数据管理（建工程/模型/导入）”。
> 本次完成前半段：Django 工程搭建、MySQL 8.4 连接、四张模型表、迁移与运行验证。
> 目录名沿用开工时的 `项目04-Django工程搭建`，内容对应项目 04。

## 一、基本信息

| 项 | 内容 |
| --- | --- |
| 日期 | 2026-11-06 |
| 依据 | 课堂 PPT（Django 目录结构 / settings 五项配置 / check 自检 / 四个思考题） |
| 环境 | Python 3.12.7、Django 6.1.2、MySQL 8.4.3（3307）、PyMySQL 1.2.3 |
| 状态 | ✅ 工程可运行，check 通过，迁移已应用，首页可读 200 条样本 |

## 二、实际做了什么

1. **建工程与应用**：`django-admin startproject risk_project .` + `startapp risk_app`。
2. **装 MySQL 8.4**：官网 winx64 便携包解压到 `_tmp/mysql84`，初始化数据目录，跑在 3307，与 5.7（3306）并存。
3. **连库**：`risk_project/__init__.py` 注册 PyMySQL；settings 改五项（应用、数据库、模板、语言、时区）。
4. **建模型**：Enterprise（24 字段）、RiskIndicator（21 字段）、UserProfile（6 字段）、AuditLog（7 字段）。
5. **迁移**：`makemigrations risk_app` → `0001_initial.py`；`migrate` 建表 14 张（含 Django 自带）。
6. **验证**：`manage.py check` 0 issues；`/health/` 返回 MySQL 8.4.3 与表清单；首页显示 200 企业 / 200 风险。
7. **全量导入**：`data_import.py` 自动建表、清空、批量写入，两张 CSV 各 **10000 条**，实测 5.7 秒。
8. **后台验证**：admin.py 注册四个模型，支持搜索与筛选；另建 superuser `admin`。
9. **数据核对**：两项记录数、关键字段非空率、经营状态与风险等级分布，见报告表 4-6。

## 三、关键配置

| 配置项 | 值 |
| --- | --- |
| `INSTALLED_APPS` | 追加 `risk_app` |
| `DATABASES` | mysql / risk_assessment / 127.0.0.1:3307 / risk_user |
| `TEMPLATES.DIRS` | `BASE_DIR/risk_app/templates` |
| `LANGUAGE_CODE` | `zh-hans` |
| `TIME_ZONE` / `USE_TZ` | `Asia/Shanghai` / `False` |

## 四、产出

| 产出 | 路径 |
| --- | --- |
| 报告（docx / pdf，15 页） | [`报告/Django工程搭建报告-249990736-薛瑞.docx`](报告/) |
| 截图（11 张） | [`截图/`](截图/) |
| 交付核对表 | [`交付核对表.md`](交付核对表.md) |
| 请求链路图（SVG + 600dpi PNG） | [`图/`](图/) |
| 工程代码 | 项目根：`manage.py`、`risk_project/`、`risk_app/` |
| 导入脚本 | [`data_import.py`](../../data_import.py)（全量 2 万条） |
| 核对脚本 | [`scripts/verify_import.py`](../../scripts/verify_import.py) |
| 第 1 周周报 | [`周报/学生实训周报-第1周-249990736-薛瑞.docx`](周报/) |
| 可视化与图片模块（3.6） | [`可视化与图片模块/README.md`](可视化与图片模块/README.md) |

## 五、常用命令

```bash
# 启动 MySQL 8.4（便携实例，未注册服务）
_tmp/mysql84/mysql-8.4.3-winx64/bin/mysqld --no-defaults \
  --basedir=... --datadir=... --port=3307 --mysql-native-password=ON

# 自检 / 迁移 / 启动
.venv/Scripts/python.exe manage.py check
.venv/Scripts/python.exe manage.py migrate
.venv/Scripts/python.exe manage.py runserver 127.0.0.1:8000
```

## 六、遗留

- MySQL 8.4 是便携实例，开机需手动启动，未注册 Windows 服务；
- 端口 3307、账号 `risk_user` 写在 settings 里，生产应改为环境变量；
- 与指导书字段数差异：指导书 enterprise 63 字段、risk_indicator 29 字段，本设计按系统设计文档裁剪为 24 / 21 字段，差异理由见报告第 6 节；
- 指导书要求 3 个模型，本项目多一个 AuditLog（审计），属扩展。

## 七、变更记录

| 日期 | 改动 |
| --- | --- |
| 2026-11-06 | 完成工程搭建、8.4 实例、模型与迁移、运行验证，出报告 |

## 八、追加：可视化与图片模块（2026-11-09）

- 企业可视化 `/chart/enterprise/`：状态饼图、注册资本区间、成立年份分布；
- 风险可视化 `/chart/risk/`：等级饼图、得分分布、Top10 表；
- 图片内容 `/chart/image/<kind>.svg`：服务端实时生成 SVG，可下载；
- 实现：`risk_app/charts.py` 纯 Python 拼 SVG，不依赖 CDN，离线可用；
- 说明：按用户要求，本次只改代码与页面，未回头修改前面的 Word 文档。
