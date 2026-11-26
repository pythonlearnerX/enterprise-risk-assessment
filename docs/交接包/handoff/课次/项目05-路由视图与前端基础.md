# 项目 05-路由视图与前端基础

> 依据：实训指导书 05《Django 路由与视图、前端 HTML 基础》
> 原则：项目 4 已有的功能（工程、模型、迁移、导入、可视化）不动，只补指导书要求但还缺的部分。

## 一、指导书要求对照

| 指导书要求 | 之前 | 本次处理 |
| --- | --- | --- |
| 根路由 include + 应用路由 + `app_name` + 路由命名 | ✅ 已有 | 保持，新增 4 条列表/详情路由 |
| `<int:pk>` 参数路由 | ❌ | ✅ 企业详情、风险详情 |
| 首页视图 | ✅ 已有 | 改为继承 base.html |
| 企业列表视图（筛选 + 分页） | ❌ | ✅ `enterprise_list` |
| 风险列表视图（筛选 + 分页） | ❌ | ✅ `risk_list` |
| 详情视图 + `get_object_or_404` | ❌ | ✅ 企业/风险详情 |
| 登录 / 退出 | ❌ | ✅ `auth_views.py` + `login.html` |
| `base.html` 模板继承（4 个 block） | ❌ | ✅ 新增，首页/列表/详情全部继承 |
| 静态文件 `style.css` / `main.js` | ❌（目录空） | ✅ 新增并被页面引用 |
| 分页保留筛选条件 | ❌ | ✅ 分页链接带 keyword/status/category/level |
| 空状态 `{% empty %}` | 部分 | ✅ 两个列表页都有 |

## 二、新增文件

| 文件 | 作用 |
| --- | --- |
| `risk_app/auth_views.py` | 登录、退出（含 next 回跳校验） |
| `risk_app/templates/base.html` | 骨架：导航、侧栏、title/content/extra_css/extra_js |
| `risk_app/templates/login.html` | 登录页 |
| `risk_app/templates/enterprise_list.html` | 企业列表：关键词 + 状态 + 类别、每页 10 条 |
| `risk_app/templates/enterprise_detail.html` | 企业详情 + 关联风险 |
| `risk_app/templates/risk_list.html` | 风险列表：关键词 + 等级、每页 10 条 |
| `risk_app/templates/risk_detail.html` | 风险详情：四维得分 + 12 项原始指标 |
| `risk_app/static/css/style.css` | 导航、侧栏、卡片、表格、分页样式 |
| `risk_app/static/js/main.js` | CSRF 读取、筛选框回车提交 |

`risk_app/views.py` 追加 4 个视图并引入 `login_required`、`Paginator`、`get_object_or_404`；`risk_app/urls.py` 追加 6 条路由（登录、退出、企业列表/详情、风险列表/详情）。

## 三、路由表（新增部分）

| URL | 视图 | 名称 | 说明 |
| --- | --- | --- | --- |
| `/login/` | `auth_views.login_view` | `login` | 登录 |
| `/logout/` | `auth_views.logout_view` | `logout` | 退出 |
| `/enterprise/list/` | `views.enterprise_list` | `enterprise_list` | 企业列表 |
| `/enterprise/detail/<int:pk>/` | `views.enterprise_detail` | `enterprise_detail` | 企业详情 |
| `/risk/list/` | `views.risk_list` | `risk_list` | 风险列表 |
| `/risk/detail/<int:pk>/` | `views.risk_detail` | `risk_detail` | 风险详情 |

全部页面视图都加了 `@login_required`，未登录访问列表会 302 跳 `/login/?next=...`。

## 四、验证结果（Django test client）

| 检查 | 结果 |
| --- | --- |
| 匿名访问 `/enterprise/list/` | 302 跳登录 |
| 登录 `admin/Admin@2026` | 成功 |
| `/` | 200，4138 bytes |
| `/enterprise/list/` | 200，共 10000 条 |
| `/enterprise/list/?keyword=重庆` | 200，9788 条 |
| `/enterprise/list/?keyword=重庆&page=2` | 200，分页链接保留 keyword |
| `/risk/list/`、`?level=high`、`?page=3` | 200 |
| 详情页（存在） | 200 |
| 详情页（不存在 id） | 404 |
| 空状态 | 显示“暂无数据” |
| 静态文件 `/static/css/style.css` | 200 |
| 无 CSRF 的 POST | 403 |

## 五、问题记录（指导书要求 ≥3 条）

| # | 现象 | 原因 | 解决 |
| --- | --- | --- | --- |
| 1 | `NoReverseMatch: Reverse for 'risk_detail' with arguments '('',)'` | 首页 `top_risks` 用 `values()` 只取了 name/score/level，没取 id，模板 `{% url %}` 拿到空参数 | `values()` 增加 `"id"`，模板传 `r.id` |
| 2 | `Forbidden (CSRF cookie not set.): /login/`，返回 403 | POST 表单没带 `{% csrf_token %}` | 登录表单加 `{% csrf_token %}`，测试客户端关闭 CSRF 校验才可脚本登录 |
| 3 | 访问 `/enterprise/detail/99999999/` 返回 404 | 用 `get_object_or_404` 按主键取对象，不存在即 404 | 属预期行为；页面列表只渲染真实存在的 id |
| 4 | 未登录访问列表被 302 到登录页 | 视图加了 `@login_required` | 属预期行为；`LOGIN_URL` 已在 settings 配好 |

## 六、截图

| 文件 | 内容 |
| --- | --- |
| `截图/01-首页.png` | 首页：统计卡片 + Top5 + 侧栏导航 |
| `截图/02-企业列表.png` | 企业列表：关键词“重庆”筛选、9788 条、分页 |
| `截图/03-风险列表.png` | 风险列表：四维得分、高风险标记、分页 |
| `截图/04-登录页.png` | 登录页 |
| `截图/05-请求链路图.png` | URL → 视图 → 模型 → 模板 → 响应（沿用项目 4 图） |

> 截图是在登录态下用 Django test client 取页面、内联 Bootstrap 与 style.css 后渲染的，效果与浏览器一致。
> 指导书另要求“开发者工具 Network 面板”截图，需在浏览器按 F12 → Network → 刷新页面自行截取，脚本无法替代。

## 七、未做/留到后面

- 企业列表的导出、批量操作：不在指导书 05 范围；
- 风险报告页、PDF：属项目 3.4/12；
- ECharts 前端图表：当前可视化用服务端 SVG，已满足展示，暂不引入 ECharts。

## 八、变更记录

| 日期 | 改动 |
| --- | --- |
| 2026-11-10 | 补登录/退出、企业/风险列表与详情、base.html、静态文件、分页筛选 |