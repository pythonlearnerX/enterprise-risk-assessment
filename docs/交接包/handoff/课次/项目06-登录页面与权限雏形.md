# 项目 06-登录页面与权限雏形

> 依据：实训指导书 06《登录页面与权限雏形》
> 原则：项目 5 已有登录/退出与 `@login_required` 骨架，本次只补指导书要求但还缺的部分。

## 一、对照指导书

| 指导书要求 | 之前 | 本次处理 |
| --- | --- | --- |
| authenticate / login / logout | ✅ 已有 | 保持 |
| 登录页（CSRF、密码掩码、错误提示） | ✅ 已有 | 重做视觉：渐变背景、记住我、测试账号提示 |
| 参数为空提示 | ❌ 未单独判断 | ✅ “用户名和密码不能为空” |
| 认证失败提示不泄露账号存在性 | ✅ 统一文案 | ✅ 实测两次提示完全一致 |
| “记住我”7 天 / 关闭浏览器失效 | ❌ 无 | ✅ `set_expiry(604800)` / `set_expiry(0)` |
| UserProfile 自动补建 | ❌ 未处理 | ✅ 登录成功 `get_or_create(role="normal")` |
| 角色字段（admin / normal） | ✅ 模型已有 | ✅ 建 `zhangsan` 普通用户，admin 置为管理员 |
| 首页 / 列表 `@login_required` | 列表有，首页无 | ✅ 首页与两个可视化页也加保护 |
| LOGIN_URL / LOGIN_REDIRECT_URL / LOGOUT_REDIRECT_URL | 只有 LOGIN_URL | ✅ 三项齐全 |
| 导航显示用户名与退出 | ✅ 已有 | ✅ 增加“（管理员）/（普通用户）”标识 |
| 菜单按角色显示 | ❌ 所有人可见后台 | ✅ 仅管理员显示“后台管理” |
| 认证流程图 | ❌ | ✅ `截图/07-认证流程图.png`（同名 SVG 可编辑） |

## 二、测试账号

| 用户名 | 密码 | 角色 | 说明 |
| --- | --- | --- | --- |
| admin | Admin@2026 | 管理员 | 超级用户，可见后台入口 |
| zhangsan | test123456 | 普通用户 | 信贷部，菜单无后台管理 |

两个账号的密码均以 `pbkdf2_sha256$` 开头，数据库无明文。

## 三、代码改动

| 文件 | 改动 |
| --- | --- |
| `risk_app/auth_views.py` | 空参数判断、记住我、`get_or_create` 补建扩展、next 安全校验 |
| `risk_app/templates/login.html` | 渐变背景、记住我复选框、测试账号提示、错误条 |
| `risk_app/templates/base.html` | 显示角色；后台入口仅管理员可见 |
| `risk_project/settings.py` | 增加 `LOGIN_REDIRECT_URL`、`LOGOUT_REDIRECT_URL` |
| `risk_app/views.py` | `index`、`chart_enterprise`、`chart_risk` 加 `@login_required` |

## 四、验证结果

| 验证项 | 结果 |
| --- | --- |
| 空参数提交 | 提示“用户名和密码不能为空” |
| 不存在的用户 vs 密码错误 | 均提示“用户名或密码错误”，文案一致 |
| 勾选记住我 | `_session_expiry=604800`，Cookie 有到期时间 |
| 不勾选 | `_session_expiry=0`，Cookie 无到期时间（关浏览器失效） |
| 未登录访问 `/enterprise/list/` | 302 → `/login/?next=/enterprise/list/` |
| 未登录访问 `/` | 302 → `/login/?next=/` |
| 登录后回跳 | 302 → `/enterprise/list/` |
| 退出 | 302 → `/login/` |
| 无 CSRF Token 的 POST | 403 |
| 密码存储 | `pbkdf2_sha256$1500000$...` |
| 普通用户菜单 | 无“后台管理” |
| 管理员菜单 | 有“后台管理”，顶部显示“管理员” |

## 五、问题记录

| # | 现象 | 原因 | 解决 |
| --- | --- | --- | --- |
| 1 | 未勾选“记住我”时会话仍显示 1209600 秒 | 用 `get_expiry_age()` 读的是默认 Cookie 时长，不是会话标记 | 改看 `_session_expiry`（0）与 Cookie 是否有 expires，确认关浏览器失效 |
| 2 | 登录后回到登录页 | 早期表单 action 写死、next 未传 | 表单带 hidden next，视图校验后 `redirect(next_url)` |
| 3 | 普通用户也能看到“后台管理” | 菜单未按角色判断 | 模板加 `user.is_superuser or user.profile.role == 'admin'` |
| 4 | 缺 UserProfile 时模板访问 `user.profile` 报错 | 用户创建时没建扩展记录 | 登录成功自动 `get_or_create`，并给 admin/zhangsan 补记录 |

## 六、截图

| 文件 | 内容 |
| --- | --- |
| `01-登录页.png` | 渐变背景、记住我、测试账号提示 |
| `02-错误提示.png` | 空参数提交后的红色提示条 |
| `03-登录后首页-普通用户.png` | zhangsan 登录，顶部“普通用户”，无后台菜单 |
| `04-未登录跳转302.png` | 两个受限地址 302 与 next 参数 |
| `05-密码哈希.png` | auth_user 中两个账号的 pbkdf2 前缀 |
| `06-CSRF-403.png` | 无 Token 的 POST 返回 403 |
| `07-认证流程图.png` | 表单 → authenticate → login → 会话 → 中间件还原 |
| `08-管理员首页对比.png` | admin 登录，顶部“管理员”，可见后台菜单 |

## 七、未做

- 注册、修改密码、失败次数锁定属指导书“扩展任务（选做）”，本次未做；
- `@admin_required` 数据级权限留到项目 13。

## 八、汇报材料

- `汇报/登录页面与权限雏形-汇报.pdf`（10 页，16:9）
- `汇报/讲稿.md`（约 5 分钟逐页讲稿）

## 九、变更记录

| 日期 | 改动 |
| --- | --- |
| 2026-11-10 | 补记住我、空参数、扩展补建、角色菜单、首页保护、安全验证与截图 |