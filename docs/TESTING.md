# 测试说明（TESTING）

> 80 条自动化用例，19 个测试类，单次约 12 秒。本文件说明结构、跑法、以及「要加用例时照着哪个模板写」。

---

## 一、跑法与口径

```bash
python manage.py test risk_app                 # 全量
python manage.py test risk_app.tests.RiskCalcTests   # 单个类
python manage.py test risk_app -v 2            # 看每条用例名
```

- 测试框架：Django 自带 `TestCase`（会建独立测试库，跑完销毁）。
- 数据库：与开发库同一实例，库名由 Django 自动加前缀 `test_`。
- 不依赖模板的纯逻辑用例用 `SimpleTestCase`（如 `RiskCalcTests`），不建库、跑得更快。

---

## 二、19 个测试类（按模块）

| 测试类 | 条数 | 覆盖点 |
| --- | --- | --- |
| `AuthTests` | 4 | 登录页、未登录跳转带 next、角色分流、用户管理权限 |
| `DataTests` | 3 | 数据量、分数边界、图表接口结构 |
| `AITests` | 2 | AI 配置读写、风险解读接口 |
| `FeatureTests` | 4 | 对比页、CSV 导出、详情页百分位 |
| `AlertTests` | 3 | 规则新增、启停、命中计数 |
| `ChartUpgradeTests` | 4 | 图表接口结构、导出、主题 |
| `DrilldownTests` | 4 | 统计卡下钻链接、筛选条件传递 |
| `RiskCalcTests` | 7 | 两种口径、阈值、负分、权重、非法模式（**SimpleTestCase**） |
| `ReportPdfTests` | 2 | PDF 字节头与中文文件名、CSV 命名 |
| `ABStatTests` | 5 | 分桶稳定性、两比例检验、样本量 |
| `ABFlowTests` | 4 | 曝光去重、转化记录、后台页权限 |
| `DataSyncTests` | 3 | **改分后等级同步**、接口同步 |
| `AnalyticsTests` | 2 | 看板数据结构与关键指标 |
| `AIInsightTests` | 4 | 无 Key 提示、落库、权限、按钮渲染 |
| `MapTests` | 3 | 地图页、区县接口、区县筛选 |
| `MenuPermissionTests` | 7 | 菜单可见性、active、装饰器、403 页 |
| `ComparePickerTests` | 6 | 页内选企业、移除、搜索、**多值参数** |
| `HomeMergeTests` | 6 | 首页三块、每图 AI 按钮、A/B 菜单可见性 |
| `LocalModelTests` | 7 | 微服务页面、降级、空文本、高亮转义 |

合计 **80** 条。

---

## 三、加用例的模板

`risk_app/tests.py` 里已有基类 `BaseData`：它建了两类账号、批量样例企业、样例风险记录。新用例直接继承：

```python
class MyFeatureTests(BaseData):
    def test_xxx(self):
        self.client.force_login(self.user)          # self.user 普通用户，self.admin 超管
        resp = self.client.get("/enterprise/list/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "企业信息")
```

纯逻辑（不碰数据库）用 `SimpleTestCase`：

```python
class MyCalcTests(SimpleTestCase):
    def test_formula(self):
        from risk_app.risk_calc import calc_risk
        ...
```

---

## 四、这个项目验证过的「值得写成用例」的点

写完功能后，下面这些点最容易被忽略、也最容易回归：

1. **改分数后等级是否同步**（D-01 的回归）；
2. **分页后筛选条件是否还在**（`qs_suffix`）；
3. **多选参数是否取到全部**（`getlist`）；
4. **未登录访问受限页**：应是 302 带 `next`，不是 500；
5. **普通用户访问管理页**：应是 403，不是跳登录页；
6. **接口返回结构**（前端依赖 key 名，改名会静默失效）；
7. **PDF 字节头**：合并流的 `FileResponse` 没有 `.content`，要 `b"".join(resp.streaming_content)`。

---

## 五、手工测试清单（自动化覆盖不到的部分）

| 项 | 怎么做 | 期望 |
| --- | --- | --- |
| 图表渲染 | 打开 `/chart/risk/` | 饼图、柱图、雷达正常，悬停有数值 |
| 地图 | 打开 `/chart/map/` | 重庆 38 区县着色，点区县能下钻 |
| 导出 CSV | 企业列表点「导出 CSV」 | Excel 打开不乱码，行数与筛选结果一致 |
| PDF 报告 | 风险详情点「导出 PDF」 | 中文正常、文件名是中文不乱码 |
| 降级 | 停掉 NLP 容器后再打开 `/model/show/` | 页面提示服务未启动，不报 500 |
| 权限 | 用普通账号直接敲 `/console/` | 403 页，有「返回首页」按钮 |

---

## 六、测试与报告的对应关系

`课次/项目16-系统测试报告/` 里的六大模块汇总表就是按本文件第二节的类归并出来的：

| 报告中的模块 | 对应测试类 | 条数 |
| --- | --- | --- |
| 企业数据管理 | DataTests / FeatureTests / DrilldownTests / ComparePickerTests | 17 |
| 数据可视化 | ChartUpgradeTests / AnalyticsTests / MapTests / HomeMergeTests / ABStatTests / ABFlowTests | 24 |
| 风险计算与报告 | RiskCalcTests / ReportPdfTests / DataSyncTests / AlertTests | 15 |
| 用户登录与权限 | AuthTests / MenuPermissionTests | 11 |
| AI 风险预估 | AITests / AIInsightTests | 6 |
| 模型部署展示 | LocalModelTests | 7 |

改用例后记得同步报告表格（数字要对得上）。